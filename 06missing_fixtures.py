import sqlite3
import logging
from datetime import datetime
import requests
import time

# Logging beállítása
logging.basicConfig(
    filename='football_api.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_odds_data(fixture_id, headers):
    url = "https://api-football-v1.p.rapidapi.com/v3/odds"
    querystring = {
        "fixture": str(fixture_id),
        "bet": "1"
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"API hiba a fixture {fixture_id} lekérésénél: {str(e)}")
        return None

def save_odds_to_db(cursor, match_data):
    try:
        if not match_data.get('response'):
            return False
            
        match = match_data['response'][0]
        league = match['league']
        fixture = match['fixture']
        
        for bookmaker in match['bookmakers']:
            for bet in bookmaker['bets']:
                for value in bet['values']:
                    cursor.execute('''
                    INSERT INTO alldownloadoddmapping 
                    (league_id, league_name, league_country, league_logo, 
                    league_flag, league_season, fixture_id, fixture_timezone,
                    fixture_date, fixture_timestamp, update_time, bookmaker_id,
                    bookmaker_name, bet_id, bet_name, bet_value, odd)
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
        return True
    except Exception as e:
        logging.error(f"Hiba az odds adatok mentése közben: {str(e)}")
        return False

try:
    # Adatbázis kapcsolat létrehozása
    conn = sqlite3.connect('football.db')
    cursor = conn.cursor()

    # Hiányzó fixture_id-k lekérdezése
    cursor.execute('''
    SELECT 
        o.fixture_id,
        o.league_id,
        o.league_season,
        o.update_time
    FROM oddmapping o
    LEFT JOIN alldownloadoddmapping a ON o.fixture_id = a.fixture_id
    WHERE a.fixture_id IS NULL
    ORDER BY o.league_id, o.league_season, o.fixture_id
    ''')

    missing_fixtures = cursor.fetchall()
    
    if not missing_fixtures:
        logging.info("Nincs hiányzó fixture_id az alldownloadoddmapping táblában")
        print("Nincs hiányzó fixture_id az alldownloadoddmapping táblában")
    else:
        logging.info(f"Összesen {len(missing_fixtures)} hiányzó fixture_id található")
        print(f"\nÖsszesen {len(missing_fixtures)} hiányzó fixture_id található\n")
        
        # API konfiguráció
        headers = {
            "x-rapidapi-key": "2f8f06c5cemsh53de2dcfae72bbep1385ccjsnc72b018bc91a",
            "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
        }
        
        successful_updates = 0
        failed_updates = 0
        
        # Liga és szezon szerinti csoportosítás
        current_league = None
        current_season = None
        
        for fixture in missing_fixtures:
            fixture_id, league_id, season, update_time = fixture
            
            # Új liga vagy szezon esetén fejléc kiírása
            if league_id != current_league or season != current_season:
                print(f"\nLiga ID: {league_id}, Szezon: {season}")
                print("-" * 50)
                current_league = league_id
                current_season = season
            
            # Fixture adatok kiírása
            print(f"Fixture ID: {fixture_id}, Utolsó frissítés: {update_time}")
            logging.info(f"Hiányzó fixture lekérdezése - Liga: {league_id}, Szezon: {season}, Fixture ID: {fixture_id}")
            
            # Odds adatok lekérése és mentése
            odds_data = get_odds_data(fixture_id, headers)
            if odds_data and save_odds_to_db(cursor, odds_data):
                successful_updates += 1
                print(f"✓ Sikeres lekérdezés és mentés: {fixture_id}")
                conn.commit()
            else:
                failed_updates += 1
                print(f"✗ Sikertelen lekérdezés vagy mentés: {fixture_id}")
            
            # Várakozás az API rate limit miatt
            time.sleep(1)
        
        # Összesítés
        print(f"\nFeldolgozás befejezve:")
        print(f"Sikeres frissítések: {successful_updates}")
        print(f"Sikertelen frissítések: {failed_updates}")
        logging.info(f"Feldolgozás befejezve - Sikeres: {successful_updates}, Sikertelen: {failed_updates}")

except sqlite3.Error as e:
    error_msg = f"Adatbázis hiba történt: {str(e)}"
    logging.error(error_msg)
    print(error_msg)
except Exception as e:
    error_msg = f"Váratlan hiba történt: {str(e)}"
    logging.error(error_msg)
    print(error_msg)
finally:
    if 'conn' in locals():
        conn.close()
        logging.info("Adatbázis kapcsolat lezárva")
