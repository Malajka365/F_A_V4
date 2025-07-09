import sqlite3
import logging
import traceback
from datetime import datetime
from collections import defaultdict
import os

# Log könyvtár létrehozása, ha nem létezik
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Log fájl neve időbélyeggel
log_filename = os.path.join(log_dir, f'pr_calculator_this_season_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

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

def create_pr_tables():
    """PR számításhoz szükséges táblák létrehozása"""
    try:
        conn = sqlite3.connect('football.db')
        cursor = conn.cursor()
        
        # PR helper tábla létrehozása
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pr_helper_this_season (
                pr_diff DECIMAL(10,1),
                total_matches INTEGER,
                home_wins INTEGER,
                draws INTEGER,
                away_wins INTEGER,
                home_win_percentage DECIMAL(5,2),
                draw_percentage DECIMAL(5,2),
                away_win_percentage DECIMAL(5,2)
            )
        ''')
        
        # PR értékek tárolása
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_pr_data_this_season (
                fixture_id INTEGER PRIMARY KEY,
                home_pr DECIMAL(10,2),
                away_pr DECIMAL(10,2),
                pr_diff DECIMAL(10,1),
                home_win_prob DECIMAL(5,2),
                draw_prob DECIMAL(5,2),
                away_win_prob DECIMAL(5,2),
                include_in_stats BOOLEAN DEFAULT 1,
                FOREIGN KEY (fixture_id) REFERENCES fixtures(id)
            )
        ''')
        
        conn.commit()
        logger.info("PR táblák sikeresen létrehozva (this_season)")
    except Exception as e:
        logger.error(f"Hiba a táblák létrehozásakor (this_season): {str(e)}")
    finally:
        conn.close()

def calculate_power_rankings():
    """Power Rankings számítása"""
    try:
        conn = sqlite3.connect('football.db')
        cursor = conn.cursor()
        
        # Kezdeti értékek beállítása
        current_team_ratings = {}
        adjuster = 0.25
        
        # Csapatok mérkőzésszámának követése szezonok szerint
        team_matches_per_season = defaultdict(lambda: defaultdict(int))
        
        logger.info("Power Rankings számítás kezdése (this_season)")
        
        # Összes mérkőzés lekérése időrendi sorrendben
        cursor.execute('''
            SELECT id, league_id, league_season, home_team_id, away_team_id, 
                   goals_home, goals_away, date
            FROM fixtures
            ORDER BY date ASC
        ''')
        matches = cursor.fetchall()
        
        # PR számítás mérkőzésenként
        for match in matches:
            match_id, league_id, season, home_id, away_id, goals_home, goals_away, date = match
            
            # Kezdeti PR értékek beállítása ha még nem léteznek
            if home_id not in current_team_ratings:
                current_team_ratings[home_id] = 10.0
                logger.info(f"Új csapat hozzáadva (home): {home_id}, kezdeti PR: 10.0")
            if away_id not in current_team_ratings:
                current_team_ratings[away_id] = 10.0
                logger.info(f"Új csapat hozzáadva (away): {away_id}, kezdeti PR: 10.0")
            
            # Mérkőzésszám növelése mindkét csapatnál az adott szezonban, csak ha van eredmény
            if goals_home is not None and goals_away is not None:
                team_matches_per_season[f"{home_id}_{season}"][league_id] += 1
                team_matches_per_season[f"{away_id}_{season}"][league_id] += 1
            
            # Ellenőrizzük, hogy mindkét csapat játszott-e már 5 meccset ebben a szezonban
            home_matches = sum(team_matches_per_season[f"{home_id}_{season}"].values())
            away_matches = sum(team_matches_per_season[f"{away_id}_{season}"].values())
            include_in_stats = home_matches > 5 and away_matches > 5
            
            # A mérkőzés ELŐTTI PR értékek mentése
            home_pr = current_team_ratings[home_id]
            away_pr = current_team_ratings[away_id]
            pr_diff = round(home_pr - away_pr, 1)
            
            # PR értékek mentése a mérkőzéshez az AKTUÁLIS értékekkel
            cursor.execute('''
                INSERT OR REPLACE INTO match_pr_data_this_season 
                (fixture_id, home_pr, away_pr, pr_diff, include_in_stats)
                VALUES (?, ?, ?, ?, ?)
            ''', (match_id, home_pr, away_pr, pr_diff, include_in_stats))
            
            # PR változás számítása és frissítése CSAK a mentés UTÁN
            if goals_home is not None and goals_away is not None:
                goal_diff = goals_home - goals_away
                pr_change = (goal_diff - (home_pr - away_pr) - 2 * adjuster) * adjuster
                
                # PR értékek frissítése a következő mérkőzésekhez
                current_team_ratings[home_id] += pr_change
                current_team_ratings[away_id] -= pr_change
                
                logger.info(f"Mérkőzés feldolgozva: {match_id}, PR változás: {pr_change:.2f}")
                logger.info(f"Új PR értékek - {home_id}: {current_team_ratings[home_id]:.2f}, {away_id}: {current_team_ratings[away_id]:.2f}")
        
        conn.commit()
        logger.info("Power Rankings számítás befejezve (this_season)")
        
        # PR diff statisztikák számítása
        calculate_pr_diff_statistics(cursor)
        
        # Végeredmény valószínűségek frissítése
        update_match_probabilities(cursor)
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"Hiba a Power Rankings számításakor (this_season): {str(e)}")
        traceback.print_exc()
    finally:
        conn.close()

def calculate_pr_diff_statistics(cursor):
    """PR különbségek statisztikáinak számítása"""
    try:
        logger.info("PR különbségek statisztikáinak számítása kezdődik (this_season)")
        
        # PR helper tábla ürítése
        cursor.execute('DELETE FROM pr_helper_this_season')
        
        # Statisztikák számítása csak azoknál a mérkőzéseknél, ahol include_in_stats = 1
        cursor.execute('''
            WITH match_results AS (
                SELECT 
                    ROUND(m.pr_diff, 1) as pr_diff,
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN f.goals_home > f.goals_away THEN 1 ELSE 0 END) as home_wins,
                    SUM(CASE WHEN f.goals_home = f.goals_away THEN 1 ELSE 0 END) as draws,
                    SUM(CASE WHEN f.goals_home < f.goals_away THEN 1 ELSE 0 END) as away_wins
                FROM match_pr_data_this_season m
                JOIN fixtures f ON m.fixture_id = f.id
                WHERE f.goals_home IS NOT NULL 
                AND f.goals_away IS NOT NULL
                AND m.include_in_stats = 1
                GROUP BY ROUND(m.pr_diff, 1)
            )
            INSERT INTO pr_helper_this_season
            SELECT 
                pr_diff,
                total_matches,
                home_wins,
                draws,
                away_wins,
                ROUND(CAST(home_wins AS FLOAT) / total_matches * 100, 2) as home_win_percentage,
                ROUND(CAST(draws AS FLOAT) / total_matches * 100, 2) as draw_percentage,
                ROUND(CAST(away_wins AS FLOAT) / total_matches * 100, 2) as away_win_percentage
            FROM match_results
            ORDER BY pr_diff
        ''')
        
        logger.info("PR különbségek statisztikái sikeresen kiszámítva (this_season)")
        
    except Exception as e:
        logger.error(f"Hiba a PR különbségek statisztikáinak számításakor (this_season): {str(e)}")

def update_match_probabilities(cursor):
    """Mérkőzések végeredmény valószínűségeinek frissítése"""
    try:
        logger.info("Mérkőzés valószínűségek frissítése kezdődik (this_season)")
        
        cursor.execute('''
            UPDATE match_pr_data_this_season
            SET 
                home_win_prob = (
                    SELECT home_win_percentage
                    FROM pr_helper_this_season
                    WHERE ROUND(pr_helper_this_season.pr_diff, 1) = ROUND(match_pr_data_this_season.pr_diff, 1)
                ),
                draw_prob = (
                    SELECT draw_percentage
                    FROM pr_helper_this_season
                    WHERE ROUND(pr_helper_this_season.pr_diff, 1) = ROUND(match_pr_data_this_season.pr_diff, 1)
                ),
                away_win_prob = (
                    SELECT away_win_percentage
                    FROM pr_helper_this_season
                    WHERE ROUND(pr_helper_this_season.pr_diff, 1) = ROUND(match_pr_data_this_season.pr_diff, 1)
                )
        ''')
        
        logger.info("Mérkőzés valószínűségek sikeresen frissítve (this_season)")
        
    except Exception as e:
        logger.error(f"Hiba a mérkőzés valószínűségek frissítésekor (this_season): {str(e)}")

if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("PR Calculator indítása (this_season)")
        logger.info(f"Futtatás időpontja: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        create_pr_tables()
        calculate_power_rankings()
        
        logger.info("PR Calculator futás sikeresen befejezve (this_season)")
        logger.info("=" * 50)
    except Exception as e:
        logger.error("A program futása hibával leállt!")
        logger.error(traceback.format_exc())
        raise
