import sqlite3
import logging
from datetime import datetime

# Logging beállítása
logging.basicConfig(
    filename='football_api.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def create_odds_history_table(cursor):
    try:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS odds_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id INTEGER,
            bookmaker_id INTEGER,
            bet_value TEXT,
            odd REAL,
            update_time TEXT,
            league_id INTEGER,
            league_name TEXT,
            league_season INTEGER,
            FOREIGN KEY (fixture_id) REFERENCES alldownloadoddmapping(fixture_id)
        )
        ''')
        logging.info("odds_history tábla létrehozva vagy már létezik")
    except sqlite3.Error as e:
        logging.error(f"Hiba az odds_history tábla létrehozásakor: {str(e)}")
        raise

try:
    # Adatbázis kapcsolat létrehozása
    conn = sqlite3.connect('football.db')
    cursor = conn.cursor()

    # Odds history tábla létrehozása
    create_odds_history_table(cursor)

    # Előző odds értékek áthelyezése
    cursor.execute('''
    INSERT INTO odds_history (
        fixture_id,
        bookmaker_id,
        bet_value,
        odd,
        update_time,
        league_id,
        league_name,
        league_season
    )
    SELECT 
        fixture_id,
        bookmaker_id,
        bet_value,
        previous_odd,
        previous_update_time,
        league_id,
        league_name,
        league_season
    FROM alldownloadoddmapping
    WHERE previous_odd IS NOT NULL 
    AND previous_update_time IS NOT NULL
    ''')

    migrated_rows = cursor.rowcount
    logging.info(f"Sikeresen átmásolva {migrated_rows} előzmény rekord az odds_history táblába")
    print(f"Sikeresen átmásolva {migrated_rows} előzmény rekord az odds_history táblába")

    # Previous oszlopok nullázása
    cursor.execute('''
    UPDATE alldownloadoddmapping
    SET previous_odd = NULL,
        previous_update_time = NULL
    WHERE previous_odd IS NOT NULL 
    OR previous_update_time IS NOT NULL
    ''')

    cleared_rows = cursor.rowcount
    logging.info(f"Sikeresen törölve {cleared_rows} előzmény adat az alldownloadoddmapping táblából")
    print(f"Sikeresen törölve {cleared_rows} előzmény adat az alldownloadoddmapping táblából")

    # Változtatások mentése
    conn.commit()
    logging.info("Migráció sikeresen befejezve")
    print("Migráció sikeresen befejezve")

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
