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

def get_odds_data(league_id, season, headers):
    url = "https://api-football-v1.p.rapidapi.com/v3/odds"
    all_responses = []
    page = 1
    
    while True:
        querystring = {
            "league": str(league_id),
            "season": str(season),
            "bet": "1",
            "page": str(page)
        }
        
        try:
            response = requests.get(url, headers=headers, params=querystring)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('response'):
                break
                
            all_responses.extend(data['response'])
            
            # Ellenőrizzük, hogy van-e még további oldal
            paging = data.get('paging', {})
            current_page = paging.get('current', 1)
            total_pages = paging.get('total', 1)
            
            logging.info(f"Liga {league_id}, Szezon {season}: {page}/{total_pages} oldal feldolgozva")
            
            if current_page >= total_pages:
                break
                
            page += 1
            time.sleep(1)  # Várakozás az oldalak között
            
        except requests.exceptions.RequestException as e:
            logging.error(f"API hiba a liga {league_id}, szezon {season}, oldal {page} lekérésénél: {str(e)}")
            break
    
    return {"response": all_responses} if all_responses else None

def save_to_history(cursor, fixture_id, bookmaker_id, bet_value, odd, update_time, league_id, league_name, league_season):
    try:
        cursor.execute('''
        INSERT INTO odds_history 
        (fixture_id, bookmaker_id, bet_value, odd, update_time, league_id, league_name, league_season)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (fixture_id, bookmaker_id, bet_value, odd, update_time, league_id, league_name, league_season))
    except sqlite3.Error as e:
        logging.error(f"Hiba a történeti adat mentésekor: {str(e)}")
        raise

def update_odds_data(cursor, fixture_id, bookmaker_id, bet_value, new_odd, new_update_time, league_id, league_name, league_season):
    try:
        # Először mentsük el az aktuális értéket a history táblába
        cursor.execute('''
        SELECT odd, update_time 
        FROM alldownloadoddmapping 
        WHERE fixture_id = ? AND bookmaker_id = ? AND bet_value = ?
        ''', (fixture_id, bookmaker_id, bet_value))
        
        current_data = cursor.fetchone()
        if current_data:
            current_odd, current_update = current_data
            save_to_history(cursor, fixture_id, bookmaker_id, bet_value, current_odd, 
                          current_update, league_id, league_name, league_season)
        
        # Frissítsük az aktuális értéket
        cursor.execute('''
            UPDATE alldownloadoddmapping 
            SET odd = ?,
                update_time = ?
            WHERE fixture_id = ? AND bookmaker_id = ? AND bet_value = ?
        ''', (new_odd, new_update_time, fixture_id, bookmaker_id, bet_value))
        
    except sqlite3.Error as e:
        logging.error(f"Hiba az odds frissítésekor: {str(e)}")
        raise

try:
    # Adatbázis kapcsolat létrehozása
    conn = sqlite3.connect('football.db')
    cursor = conn.cursor()

    # Táblák létrehozása/módosítása
    create_odds_history_table(cursor)

    # Frissítendő mérkőzések és liga-szezon párok lekérdezése
    cursor.execute('''
    WITH UpdateNeededFixtures AS (
        SELECT DISTINCT 
            o.fixture_id,
            o.league_id,
            o.league_season,
            o.update_time as oddmapping_update,
            a.update_time as alldownload_update
        FROM oddmapping o
        LEFT JOIN (
            SELECT fixture_id, MAX(update_time) as update_time
            FROM alldownloadoddmapping
            GROUP BY fixture_id
        ) a ON o.fixture_id = a.fixture_id
        WHERE a.update_time IS NULL
        OR datetime(o.update_time) > datetime(a.update_time)
    )
    SELECT 
        league_id,
        league_season,
        COUNT(fixture_id) as fixtures_to_update,
        GROUP_CONCAT(fixture_id) as fixture_ids,
        GROUP_CONCAT(oddmapping_update) as update_times
    FROM UpdateNeededFixtures
    GROUP BY league_id, league_season
    ''')

    leagues_to_update = cursor.fetchall()
    
    if not leagues_to_update:
        logging.info("Nincs frissítendő adat")
        exit(0)

    logging.info(f"Frissítendő liga-szezon párok száma: {len(leagues_to_update)}")

    # API konfiguráció
    headers = {
        "x-rapidapi-key": "2f8f06c5cemsh53de2dcfae72bbep1385ccjsnc72b018bc91a",
        "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
    }

    # Liga-szezon párok feldolgozása
    for league_id, season, fixtures_count, fixture_ids, _ in leagues_to_update:
        logging.info(f"Odds adatok frissítése: liga ID {league_id}, szezon {season}, {fixtures_count} mérkőzés, Fixture ID-k: {fixture_ids}")
        
        data = get_odds_data(league_id, season, headers)
        if not data or 'response' not in data:
            continue

        # Mérkőzések feldolgozása
        fixture_ids_list = [int(fid) for fid in fixture_ids.split(',')]
        for match in data['response']:
            try:
                fixture_id = match['fixture']['id']
                
                # Csak azokat a mérkőzéseket dolgozzuk fel, amelyeknek frissebb az update_time-ja
                if fixture_id not in fixture_ids_list:
                    continue

                league = match['league']
                fixture = match['fixture']
                
                # Minden bookmaker és odds feldolgozása
                for bookmaker in match['bookmakers']:
                    for bet in bookmaker['bets']:
                        for value in bet['values']:
                            # Ellenőrizzük, hogy létezik-e már ez a kombináció
                            cursor.execute('''
                                SELECT COUNT(*) 
                                FROM alldownloadoddmapping 
                                WHERE fixture_id = ? AND bookmaker_id = ? AND bet_value = ?
                            ''', (fixture_id, bookmaker['id'], value['value']))
                            
                            exists = cursor.fetchone()[0] > 0
                            
                            if exists:
                                # Frissítés
                                update_odds_data(
                                    cursor,
                                    fixture_id,
                                    bookmaker['id'],
                                    value['value'],
                                    float(value['odd']),
                                    match['update'],
                                    league['id'],
                                    league['name'],
                                    league['season']
                                )
                            else:
                                # Új rekord beszúrása
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
                                
                                # Az első értéket is mentsük el a history-ba
                                save_to_history(
                                    cursor,
                                    fixture_id,
                                    bookmaker['id'],
                                    value['value'],
                                    float(value['odd']),
                                    match['update'],
                                    league['id'],
                                    league['name'],
                                    league['season']
                                )

            except Exception as e:
                logging.error(f"Hiba a mérkőzés (ID: {fixture_id}) adatainak frissítése közben: {str(e)}")
                continue

        conn.commit()
        logging.info(f"Sikeresen frissítve az odds adatok a {league_id} liga {season} szezonjához")
        
        # Várakozás az API rate limit miatt
        time.sleep(1)

    logging.info("Az összes frissítés sikeresen megtörtént")

except sqlite3.Error as e:
    logging.error(f"Adatbázis hiba történt: {str(e)}")
except Exception as e:
    logging.error(f"Váratlan hiba történt: {str(e)}")
finally:
    if 'conn' in locals():
        conn.close()
        logging.info("Adatbázis kapcsolat lezárva")
