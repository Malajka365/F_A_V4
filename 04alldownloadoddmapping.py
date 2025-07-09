import requests
import sqlite3
import logging
from datetime import datetime
import time
import json

# Logging beállítása
logging.basicConfig(
    filename='football_api.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_alldownloadoddmapping_table(cursor):
    cursor.execute('''DROP TABLE IF EXISTS alldownloadoddmapping''')
    cursor.execute('''
    CREATE TABLE alldownloadoddmapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        league_id INTEGER,
        league_name TEXT,
        league_country TEXT,
        league_logo TEXT,
        league_flag TEXT,
        league_season INTEGER,
        fixture_id INTEGER,
        fixture_timezone TEXT,
        fixture_date TEXT,
        fixture_timestamp INTEGER,
        update_time TEXT,
        bookmaker_id INTEGER,
        bookmaker_name TEXT,
        bet_id INTEGER,
        bet_name TEXT,
        bet_value TEXT,
        odd REAL,
        UNIQUE(fixture_id, bookmaker_id, bet_value)
    )
    ''')

def get_odds_data(league_id, season, headers):
    url = "https://api-football-v1.p.rapidapi.com/v3/odds"
    querystring = {
        "league": str(league_id),
        "season": str(season),
        "bet": "1"  # Match Winner odds
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"API hiba a liga {league_id}, szezon {season} lekérésénél: {str(e)}")
        return None

try:
    # Adatbázis kapcsolat létrehozása
    conn = sqlite3.connect('football.db')
    cursor = conn.cursor()
    
    # Új tábla létrehozása
    create_alldownloadoddmapping_table(cursor)

    # Liga ID és szezon kombinációk lekérdezése
    cursor.execute('''
    SELECT DISTINCT league_id, league_season 
    FROM oddmapping
    ''')
    
    combinations = cursor.fetchall()
    logging.info(f"Talált liga-szezon kombinációk száma: {len(combinations)}")

    # API konfiguráció
    headers = {
        "x-rapidapi-key": "2f8f06c5cemsh53de2dcfae72bbep1385ccjsnc72b018bc91a",
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }

    total_fixtures_processed = 0
    
    # Minden liga-szezon kombinációra lekérjük az odds adatokat
    for league_id, season in combinations:
        logging.info(f"Odds adatok lekérése: liga ID {league_id}, szezon {season}")
        
        data = get_odds_data(league_id, season, headers)
        if not data or 'response' not in data:
            continue

        # Adatok feldolgozása és mentése
        for match in data['response']:
            try:
                league = match['league']
                fixture = match['fixture']
                
                # Minden bookmaker és odds feldolgozása
                for bookmaker in match['bookmakers']:
                    for bet in bookmaker['bets']:
                        for value in bet['values']:
                            cursor.execute('''
                            INSERT OR REPLACE INTO alldownloadoddmapping 
                            (league_id, league_name, league_country, league_logo, league_flag, 
                             league_season, fixture_id, fixture_timezone, fixture_date, 
                             fixture_timestamp, update_time, bookmaker_id, bookmaker_name,
                             bet_id, bet_name, bet_value, odd)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                league['id'],
                                league['name'],
                                league['country'],
                                league['logo'],
                                league['flag'],
                                league['season'],
                                fixture['id'],
                                fixture['timezone'],
                                fixture['date'],
                                fixture['timestamp'],
                                match['update'],
                                bookmaker['id'],
                                bookmaker['name'],
                                bet['id'],
                                bet['name'],
                                value['value'],
                                float(value['odd'])
                            ))
                
                total_fixtures_processed += 1
                
            except Exception as e:
                logging.error(f"Hiba a mérkőzés adatainak mentése közben: {str(e)}")
                continue

        conn.commit()
        logging.info(f"Sikeresen mentve az odds adatok a {league_id} liga {season} szezonjához")
        
        # Várakozás az API rate limit miatt
        time.sleep(1)

    logging.info(f"Összesen {total_fixtures_processed} mérkőzés odds adata került mentésre")

except sqlite3.Error as e:
    logging.error(f"Adatbázis hiba történt: {str(e)}")
except Exception as e:
    logging.error(f"Váratlan hiba történt: {str(e)}")
finally:
    if 'conn' in locals():
        conn.close()
        logging.info("Adatbázis kapcsolat lezárva")
