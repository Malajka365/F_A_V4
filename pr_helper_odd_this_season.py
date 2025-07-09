import sqlite3
import logging
import traceback
from datetime import datetime
import os
import codecs

# Log könyvtár létrehozása, ha nem létezik
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Log fájl neve időbélyeggel
log_filename = os.path.join(log_dir, f'pr_helper_odd_this_season_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# File handler létrehozása UTF-8 kódolással
file_handler = logging.FileHandler(log_filename, 'w', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)

# Konzol handler létrehozása
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(console_formatter)

# Root logger konfigurálása
logger = logging.getLogger('')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def check_database_connection():
    """Adatbázis kapcsolat ellenőrzése"""
    try:
        conn = sqlite3.connect('football.db')
        cursor = conn.cursor()
        
        # Szükséges táblák ellenőrzése
        required_tables = ['match_pr_data_this_season', 'alldownloadoddmapping', 'fixtures']
        for table in required_tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                raise Exception(f"A(z) {table} tábla nem található az adatbázisban!")
        
        logger.info("Adatbázis kapcsolat és táblák ellenőrzése sikeres")
        return True
    except Exception as e:
        logger.error(f"Adatbázis ellenőrzési hiba: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def create_pr_helper_odd_tables():
    """PR Odds segédtáblák létrehozása"""
    try:
        conn = sqlite3.connect('football.db')
        cursor = conn.cursor()
        
        # Home odds segédtábla
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pr_helper_home_odd_this_season (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_diff DECIMAL(10,1),
                odd_value DECIMAL(10,2),
                total_matches INTEGER,
                win_count INTEGER,
                lose_count INTEGER,
                win_percentage DECIMAL(5,2),
                lose_percentage DECIMAL(5,2)
            )
        ''')
        
        # Home mérkőzések tábla
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pr_helper_home_matches_this_season (
                stat_id INTEGER,
                fixture_id INTEGER,
                date TEXT,
                home_team TEXT,
                away_team TEXT,
                score TEXT,
                pr_diff DECIMAL(10,1),
                odd_value DECIMAL(10,2),
                FOREIGN KEY (stat_id) REFERENCES pr_helper_home_odd_this_season(id)
            )
        ''')
        
        # Draw odds segédtábla
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pr_helper_draw_odd_this_season (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_diff DECIMAL(10,1),
                odd_value DECIMAL(10,2),
                total_matches INTEGER,
                win_count INTEGER,
                lose_count INTEGER,
                win_percentage DECIMAL(5,2),
                lose_percentage DECIMAL(5,2)
            )
        ''')
        
        # Draw mérkőzések tábla
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pr_helper_draw_matches_this_season (
                stat_id INTEGER,
                fixture_id INTEGER,
                date TEXT,
                home_team TEXT,
                away_team TEXT,
                score TEXT,
                pr_diff DECIMAL(10,1),
                odd_value DECIMAL(10,2),
                FOREIGN KEY (stat_id) REFERENCES pr_helper_draw_odd_this_season(id)
            )
        ''')
        
        # Away odds segédtábla
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pr_helper_away_odd_this_season (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_diff DECIMAL(10,1),
                odd_value DECIMAL(10,2),
                total_matches INTEGER,
                win_count INTEGER,
                lose_count INTEGER,
                win_percentage DECIMAL(5,2),
                lose_percentage DECIMAL(5,2)
            )
        ''')
        
        # Away mérkőzések tábla
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pr_helper_away_matches_this_season (
                stat_id INTEGER,
                fixture_id INTEGER,
                date TEXT,
                home_team TEXT,
                away_team TEXT,
                score TEXT,
                pr_diff DECIMAL(10,1),
                odd_value DECIMAL(10,2),
                FOREIGN KEY (stat_id) REFERENCES pr_helper_away_odd_this_season(id)
            )
        ''')
        
        conn.commit()
        logger.info("PR Odds segédtáblák sikeresen létrehozva")
    except Exception as e:
        logger.error(f"Hiba a táblák létrehozásakor: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

def create_sqlite_functions(conn):
    """SQLite függvények létrehozása"""
    def sqlite_round_to_nearest_five(value):
        if value is None:
            return None
        value_100 = round(float(value) * 100)
        last_digit = value_100 % 10
        if last_digit < 5:
            value_100 = value_100 - last_digit
        else:
            value_100 = value_100 - last_digit + 5
        return round(value_100 / 100, 2)
    
    conn.create_function("round_to_nearest_five", 1, sqlite_round_to_nearest_five)
    logger.info("SQLite függvények sikeresen létrehozva")

def calculate_pr_odd_statistics():
    """PR és odds statisztikák számítása"""
    conn = None
    try:
        if not check_database_connection():
            raise Exception("Adatbázis ellenőrzés sikertelen!")

        conn = sqlite3.connect('football.db')
        create_sqlite_functions(conn)
        cursor = conn.cursor()
        
        logger.info("Táblák ürítése kezdődik...")
        # Táblák ürítése
        tables = [
            'pr_helper_home_matches_this_season',
            'pr_helper_draw_matches_this_season',
            'pr_helper_away_matches_this_season',
            'pr_helper_home_odd_this_season',
            'pr_helper_draw_odd_this_season',
            'pr_helper_away_odd_this_season'
        ]
        for table in tables:
            cursor.execute(f'DELETE FROM {table}')
        logger.info("Táblák ürítése sikeres")
        
        # Statisztikák számítása és mentése típusonként
        bet_types = ['Home', 'Draw', 'Away']
        for bet_type in bet_types:
            logger.info(f"Statisztikák számítása {bet_type} típusra...")
            try:
                # SQL lekérdezés végrehajtása
                if bet_type == 'Home':
                    win_condition = "f.goals_home > f.goals_away"
                    lose_condition = "f.goals_home <= f.goals_away"
                    target_table = "pr_helper_home_odd_this_season"
                    matches_table = "pr_helper_home_matches_this_season"
                elif bet_type == 'Draw':
                    win_condition = "f.goals_home = f.goals_away"
                    lose_condition = "f.goals_home != f.goals_away"
                    target_table = "pr_helper_draw_odd_this_season"
                    matches_table = "pr_helper_draw_matches_this_season"
                else:  # Away
                    win_condition = "f.goals_home < f.goals_away"
                    lose_condition = "f.goals_home >= f.goals_away"
                    target_table = "pr_helper_away_odd_this_season"
                    matches_table = "pr_helper_away_matches_this_season"
                
                # Statisztikák számítása és mentése
                cursor.execute(f'''
                    INSERT INTO {target_table} (pr_diff, odd_value, total_matches, win_count, lose_count, win_percentage, lose_percentage)
                    WITH match_results AS (
                        SELECT 
                            ROUND(m.pr_diff, 1) as pr_diff,
                            round_to_nearest_five(a.odd) as odd_value,
                            COUNT(*) as total_matches,
                            SUM(CASE WHEN {win_condition} THEN 1 ELSE 0 END) as win_count,
                            SUM(CASE WHEN {lose_condition} THEN 1 ELSE 0 END) as lose_count
                        FROM match_pr_data_this_season m
                        JOIN alldownloadoddmapping a ON m.fixture_id = a.fixture_id
                        JOIN fixtures f ON m.fixture_id = f.id
                        WHERE a.bookmaker_id = '11'
                        AND a.bet_value = ?
                        AND f.goals_home IS NOT NULL 
                        AND f.goals_away IS NOT NULL
                        AND m.include_in_stats = 1
                        GROUP BY ROUND(m.pr_diff, 1), round_to_nearest_five(a.odd)
                    )
                    SELECT 
                        pr_diff,
                        odd_value,
                        total_matches,
                        win_count,
                        lose_count,
                        ROUND(CAST(win_count AS FLOAT) / total_matches * 100, 2) as win_percentage,
                        ROUND(CAST(lose_count AS FLOAT) / total_matches * 100, 2) as lose_percentage
                    FROM match_results
                    ORDER BY pr_diff, odd_value
                ''', (bet_type,))
                
                # Mérkőzések mentése az új táblákba
                cursor.execute(f'''
                    INSERT INTO {matches_table} (stat_id, fixture_id, date, home_team, away_team, score, pr_diff, odd_value)
                    SELECT 
                        s.id,
                        f.id AS fixture_id,
                        f.date,
                        f.home_team_name,
                        f.away_team_name,
                        f.goals_home || '-' || f.goals_away,
                        ROUND(m.pr_diff, 1),
                        round_to_nearest_five(a.odd)
                    FROM match_pr_data_this_season m
                    JOIN alldownloadoddmapping a ON m.fixture_id = a.fixture_id
                    JOIN fixtures f ON m.fixture_id = f.id
                    JOIN {target_table} s ON s.pr_diff = ROUND(m.pr_diff, 1) 
                        AND s.odd_value = round_to_nearest_five(a.odd)
                    WHERE a.bookmaker_id = '11'
                    AND a.bet_value = ?
                    AND f.goals_home IS NOT NULL 
                    AND f.goals_away IS NOT NULL
                    AND m.include_in_stats = 1
                ''', (bet_type,))
                
                rows_affected = cursor.rowcount
                logger.info(f"{bet_type} típus feldolgozva: {rows_affected} mérkőzés mentve")
                
            except Exception as e:
                logger.error(f"Hiba a {bet_type} típus feldolgozásakor: {str(e)}")
                logger.error(traceback.format_exc())
                raise
        
        conn.commit()
        logger.info("PR és odds statisztikák sikeresen kiszámítva és mentve")
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Kritikus hiba a PR és odds statisztikák számításakor: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("PR Helper Odd Calculator indítása")
        logger.info(f"Futtatás időpontja: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        create_pr_helper_odd_tables()
        calculate_pr_odd_statistics()
        
        logger.info("PR Helper Odd Calculator futás sikeresen befejezve")
        logger.info("=" * 50)
    except Exception as e:
        logger.error("A program futása hibával leállt!")
        logger.error(traceback.format_exc())
        raise
