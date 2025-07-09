import requests
import sqlite3
import json
import logging
from datetime import datetime

# Logging beállítása
logging.basicConfig(
    filename='football_api.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# API lekérdezés
url = "https://api-football-v1.p.rapidapi.com/v3/leagues"

headers = {
    "x-rapidapi-key": "2f8f06c5cemsh53de2dcfae72bbep1385ccjsnc72b018bc91a",
    "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
}

try:
    logging.info("API lekérdezés kezdése")
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    logging.info(f"Sikeres API lekérdezés. Státusz kód: {response.status_code}")

    # SQLite adatbázis létrehozása
    conn = sqlite3.connect('football.db')
    cursor = conn.cursor()

    # Leagues tábla létrehozása
    cursor.execute('''DROP TABLE IF EXISTS leagues''')
    cursor.execute('''
    CREATE TABLE leagues (
        id INTEGER NOT NULL,
        name TEXT,
        type TEXT,
        logo TEXT,
        country_name TEXT,
        country_code TEXT,
        country_flag TEXT,
        season_year INTEGER NOT NULL,
        season_start TEXT,
        season_end TEXT,
        season_current BOOLEAN,
        coverage_fixtures_events BOOLEAN,
        coverage_fixtures_lineups BOOLEAN,
        coverage_fixtures_statistics BOOLEAN,
        coverage_fixtures_players_statistics BOOLEAN,
        coverage_standings BOOLEAN,
        coverage_players BOOLEAN,
        coverage_top_scorers BOOLEAN,
        coverage_top_assists BOOLEAN,
        coverage_top_cards BOOLEAN,
        coverage_injuries BOOLEAN,
        coverage_predictions BOOLEAN,
        coverage_odds BOOLEAN,
        UNIQUE(id, season_year)
    )
    ''')

    # Adatok beszúrása
    for item in data['response']:
        league = item['league']
        country = item['country']
        
        # Minden szezon feldolgozása
        for season in item['seasons']:
            coverage = season['coverage'] if 'coverage' in season else None
            
            cursor.execute('''
            INSERT OR REPLACE INTO leagues VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ''', (
                league['id'],
                league['name'],
                league['type'],
                league['logo'],
                country['name'],
                country['code'],
                country['flag'],
                season['year'],
                season['start'],
                season['end'],
                season['current'],
                coverage['fixtures']['events'] if coverage and 'fixtures' in coverage else None,
                coverage['fixtures']['lineups'] if coverage and 'fixtures' in coverage else None,
                coverage['fixtures']['statistics_fixtures'] if coverage and 'fixtures' in coverage else None,
                coverage['fixtures']['statistics_players'] if coverage and 'fixtures' in coverage else None,
                coverage['standings'] if coverage else None,
                coverage['players'] if coverage else None,
                coverage['top_scorers'] if coverage else None,
                coverage['top_assists'] if coverage else None,
                coverage['top_cards'] if coverage else None,
                coverage['injuries'] if coverage else None,
                coverage['predictions'] if coverage else None,
                coverage['odds'] if coverage else None
            ))

    conn.commit()
    logging.info("Adatok sikeresen mentve az adatbázisba")

except requests.exceptions.RequestException as e:
    logging.error(f"API hiba történt: {str(e)}")
except sqlite3.Error as e:
    logging.error(f"Adatbázis hiba történt: {str(e)}")
except Exception as e:
    logging.error(f"Váratlan hiba történt: {str(e)}")
finally:
    if 'conn' in locals():
        conn.close()
        logging.info("Adatbázis kapcsolat lezárva")
