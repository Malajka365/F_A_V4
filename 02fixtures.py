import requests
import sqlite3
import logging
from datetime import datetime
import time

# Logging beállítása
logging.basicConfig(
    filename='football_api.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_fixtures_table(cursor):
    cursor.execute('''DROP TABLE IF EXISTS fixtures''')
    cursor.execute('''
    CREATE TABLE fixtures (
        id INTEGER PRIMARY KEY,
        referee TEXT,
        timezone TEXT,
        date TEXT,
        timestamp INTEGER,
        periods_first INTEGER,
        periods_second INTEGER,
        venue_id INTEGER,
        venue_name TEXT,
        venue_city TEXT,
        status_long TEXT,
        status_short TEXT,
        status_elapsed INTEGER,
        league_id INTEGER,
        league_name TEXT,
        league_country TEXT,
        league_logo TEXT,
        league_flag TEXT,
        league_season INTEGER,
        league_round TEXT,
        home_team_id INTEGER,
        home_team_name TEXT,
        home_team_logo TEXT,
        home_team_winner BOOLEAN,
        away_team_id INTEGER,
        away_team_name TEXT,
        away_team_logo TEXT,
        away_team_winner BOOLEAN,
        goals_home INTEGER,
        goals_away INTEGER,
        score_halftime_home INTEGER,
        score_halftime_away INTEGER,
        score_fulltime_home INTEGER,
        score_fulltime_away INTEGER,
        score_extratime_home INTEGER,
        score_extratime_away INTEGER,
        score_penalty_home INTEGER,
        score_penalty_away INTEGER
    )
    ''')

try:
    # Adatbázis kapcsolat létrehozása
    conn = sqlite3.connect('football.db')
    cursor = conn.cursor()
    
    # Liga ID-k lekérdezése a megadott feltételekkel
    cursor.execute('''
    SELECT id, season_year 
    FROM leagues 
    WHERE type = 'League' 
    AND coverage_odds = 1
    ''')
    
    leagues_data = cursor.fetchall()
    logging.info(f"Talált ligák száma: {len(leagues_data)}")

    # Fixtures tábla létrehozása
    create_fixtures_table(cursor)

    # API konfiguráció
    headers = {
        "x-rapidapi-key": "2f8f06c5cemsh53de2dcfae72bbep1385ccjsnc72b018bc91a",
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }

    # Mérkőzések lekérése és mentése minden ligához
    for league_id, season_year in leagues_data:
        logging.info(f"Mérkőzések lekérése: liga ID {league_id}, szezon {season_year}")
        
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        querystring = {"league": str(league_id), "season": str(season_year)}

        try:
            response = requests.get(url, headers=headers, params=querystring)
            response.raise_for_status()
            fixtures_data = response.json()

            # Mérkőzések feldolgozása és mentése
            for fixture in fixtures_data['response']:
                cursor.execute('''
                INSERT INTO fixtures VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ''', (
                    fixture['fixture']['id'],
                    fixture['fixture'].get('referee'),
                    fixture['fixture']['timezone'],
                    fixture['fixture']['date'],
                    fixture['fixture']['timestamp'],
                    fixture['fixture']['periods'].get('first'),
                    fixture['fixture']['periods'].get('second'),
                    fixture['fixture']['venue'].get('id'),
                    fixture['fixture']['venue'].get('name'),
                    fixture['fixture']['venue'].get('city'),
                    fixture['fixture']['status']['long'],
                    fixture['fixture']['status']['short'],
                    fixture['fixture']['status'].get('elapsed'),
                    fixture['league']['id'],
                    fixture['league']['name'],
                    fixture['league']['country'],
                    fixture['league']['logo'],
                    fixture['league']['flag'],
                    fixture['league']['season'],
                    fixture['league']['round'],
                    fixture['teams']['home']['id'],
                    fixture['teams']['home']['name'],
                    fixture['teams']['home']['logo'],
                    fixture['teams']['home'].get('winner'),
                    fixture['teams']['away']['id'],
                    fixture['teams']['away']['name'],
                    fixture['teams']['away']['logo'],
                    fixture['teams']['away'].get('winner'),
                    fixture['goals'].get('home'),
                    fixture['goals'].get('away'),
                    fixture['score']['halftime'].get('home'),
                    fixture['score']['halftime'].get('away'),
                    fixture['score']['fulltime'].get('home'),
                    fixture['score']['fulltime'].get('away'),
                    fixture['score']['extratime'].get('home'),
                    fixture['score']['extratime'].get('away'),
                    fixture['score']['penalty'].get('home'),
                    fixture['score']['penalty'].get('away')
                ))
            
            conn.commit()
            logging.info(f"Sikeresen mentve a mérkőzések a {league_id} ligához")
            
            # Várakozás az API rate limit miatt
            time.sleep(1)

        except requests.exceptions.RequestException as e:
            logging.error(f"API hiba a {league_id} liga lekérésénél: {str(e)}")
            continue

    logging.info("Minden mérkőzés adat sikeresen feldolgozva")

except sqlite3.Error as e:
    logging.error(f"Adatbázis hiba történt: {str(e)}")
except Exception as e:
    logging.error(f"Váratlan hiba történt: {str(e)}")
finally:
    if 'conn' in locals():
        conn.close()
        logging.info("Adatbázis kapcsolat lezárva")
