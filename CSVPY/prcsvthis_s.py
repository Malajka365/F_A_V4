import sqlite3
import csv
import os
from datetime import datetime
import logging

# Logolás beállítása
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Log fájl neve időbélyeggel
log_filename = os.path.join(log_dir, f"prcsvthis_s_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Logger beállítása
logger = logging.getLogger('prcsvthis_s')
logger.setLevel(logging.INFO)

# File handler UTF-8 kódolással
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formázó beállítása
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Handlerek hozzáadása a loggerhez
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def export_to_csv():
    try:
        # Adatbázis kapcsolat létrehozása
        conn = sqlite3.connect('football.db')
        cursor = conn.cursor()
        
        # CSV fájl neve az aktuális dátummal
        csv_filename = os.path.join('CSV', f'match_pr_data_this_season_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        
        # SQL lekérdezés az adatok összegyűjtéséhez
        query = """
        SELECT 
            f.date,
            f.league_name,
            f.league_id,
            f.home_team_name as home_team,
            f.away_team_name as away_team,
            f.goals_home,
            f.goals_away,
            pr.home_win_prob as prob_1,
            pr.draw_prob as prob_x,
            pr.away_win_prob as prob_2,
            pr.home_pr,
            pr.away_pr,
            pr.pr_diff,
            pr.include_in_stats
        FROM match_pr_data_this_season pr
        JOIN fixtures f ON pr.fixture_id = f.id
        ORDER BY f.date DESC, f.league_name, f.home_team_name
        """
        
        cursor.execute(query)
        
        # Oszlopnevek lekérése
        columns = [description[0] for description in cursor.description]
        
        # Adatok exportálása CSV-be
        logger.info(f"CSV exportálás kezdődik: {csv_filename}")
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            csvwriter = csv.writer(csvfile)
            
            # Fejléc írása
            csvwriter.writerow(columns)
            
            # Adatok írása
            csvwriter.writerows(cursor.fetchall())
        
        logger.info(f"CSV exportálás sikeresen befejeződött: {csv_filename}")
        
        # Kapcsolat lezárása
        conn.close()
        
    except Exception as e:
        logger.error(f"Hiba történt a CSV exportálás során: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        logger.info("CSV exportálás folyamat kezdődik...")
        export_to_csv()
        logger.info("CSV exportálás folyamat sikeresen befejeződött")
    except Exception as e:
        logger.error(f"A program futása során hiba történt: {str(e)}")
        exit(1)
