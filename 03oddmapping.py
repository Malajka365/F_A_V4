import requests
import sqlite3
import logging
from datetime import datetime
import time

# Logging beállítása
logging.basicConfig(
    filename='football_api.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def create_oddmapping_table(cursor):
    cursor.execute('''DROP TABLE IF EXISTS oddmapping''')
    cursor.execute('''
    CREATE TABLE oddmapping (
        league_id INTEGER,
        league_season INTEGER,
        fixture_id INTEGER PRIMARY KEY,
        fixture_date TEXT,
        fixture_timestamp INTEGER,
        update_time TEXT
    )
    ''')

def get_page_data(page, headers):
    url = "https://api-football-v1.p.rapidapi.com/v3/odds/mapping"
    querystring = {"page": str(page)}
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"API hiba a {page}. oldal lekérésénél: {str(e)}")
        return None

try:
    # Adatbázis kapcsolat létrehozása
    conn = sqlite3.connect('football.db')
    cursor = conn.cursor()
    
    # Tábla létrehozása
    create_oddmapping_table(cursor)

    # API konfiguráció
    headers = {
        "x-rapidapi-key": "2f8f06c5cemsh53de2dcfae72bbep1385ccjsnc72b018bc91a",
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }

    current_page = 1
    total_items_processed = 0
    
    while True:
        logging.info(f"{current_page}. oldal lekérése")
        
        # Oldal adatainak lekérése
        data = get_page_data(current_page, headers)
        if not data:
            break

        # Ellenőrizzük, hogy van-e adat
        if not data['response']:
            logging.info("Nincs több adat")
            break

        # Adatok feldolgozása és mentése
        for item in data['response']:
            try:
                cursor.execute('''
                INSERT OR REPLACE INTO oddmapping VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    item['league']['id'],
                    item['league']['season'],
                    item['fixture']['id'],
                    item['fixture']['date'],
                    item['fixture']['timestamp'],
                    item['update']
                ))
                total_items_processed += 1
            except Exception as e:
                logging.error(f"Hiba az adat mentése közben: {str(e)}")
                continue

        conn.commit()
        logging.info(f"Sikeresen mentve {len(data['response'])} elem a {current_page}. oldalról")

        # Ellenőrizzük, hogy van-e következő oldal
        if len(data['response']) < 100:
            logging.info("Elértük az utolsó oldalt")
            break

        current_page += 1
        # Várakozás az API rate limit miatt
        time.sleep(1)

    logging.info(f"Összesen {total_items_processed} elem került mentésre")

except sqlite3.Error as e:
    logging.error(f"Adatbázis hiba történt: {str(e)}")
except Exception as e:
    logging.error(f"Váratlan hiba történt: {str(e)}")
finally:
    if 'conn' in locals():
        conn.close()
        logging.info("Adatbázis kapcsolat lezárva")
