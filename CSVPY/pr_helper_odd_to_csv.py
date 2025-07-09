import sqlite3
import pandas as pd
import os
import logging
from datetime import datetime

# Log könyvtár létrehozása
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# CSV könyvtár létrehozása
csv_dir = 'CSV'
if not os.path.exists(csv_dir):
    os.makedirs(csv_dir)

# Log fájl beállítása
log_filename = os.path.join(log_dir, f'pr_helper_odd_to_csv_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
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

def export_tables_to_csv():
    """PR helper táblák exportálása CSV fájlokba"""
    try:
        # Kapcsolódás az adatbázishoz
        conn = sqlite3.connect('football.db')
        logger.info("Adatbázis kapcsolat létrehozva")

        # Táblák és fájlnevek
        tables = {
            'pr_helper_home_odd_this_season': 'pr_helper_home_odd_this_season.csv',
            'pr_helper_draw_odd_this_season': 'pr_helper_draw_odd_this_season.csv',
            'pr_helper_away_odd_this_season': 'pr_helper_away_odd_this_season.csv'
        }

        # Táblák exportálása
        for table_name, file_name in tables.items():
            try:
                # Adatok lekérése
                query = f"""
                    SELECT 
                        pr_diff,
                        odd_value,
                        total_matches,
                        win_count,
                        lose_count,
                        win_percentage,
                        lose_percentage
                    FROM {table_name}
                    ORDER BY pr_diff, odd_value
                """
                
                # DataFrame létrehozása
                df = pd.read_sql_query(query, conn)
                
                # CSV fájl útvonala
                csv_path = os.path.join(csv_dir, file_name)
                
                # Exportálás CSV-be
                df.to_csv(csv_path, index=False, encoding='utf-8-sig')
                
                # Statisztikák
                row_count = len(df)
                logger.info(f"{table_name} exportálva: {csv_path} ({row_count} sor)")
                
            except Exception as e:
                logger.error(f"Hiba a {table_name} exportálásakor: {str(e)}")
                raise

        logger.info("Minden tábla sikeresen exportálva CSV formátumba")

    except Exception as e:
        logger.error(f"Kritikus hiba az exportálás során: {str(e)}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()
            logger.info("Adatbázis kapcsolat lezárva")

if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("PR Helper Odd CSV Exporter indítása")
        logger.info(f"Futtatás időpontja: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        export_tables_to_csv()
        
        logger.info("CSV exportálás sikeresen befejezve")
        logger.info("=" * 50)
    except Exception as e:
        logger.error("A program futása hibával leállt!")
        logger.error(str(e))
        raise
