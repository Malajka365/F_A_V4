import subprocess
import os
import sys
import logging
from datetime import datetime

# Log könyvtár létrehozása, ha nem létezik
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Log fájl neve időbélyeggel
log_filename = os.path.join(log_dir, f'startupdate_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# File handler létrehozása UTF-8 kódolással
file_handler = logging.FileHandler(log_filename, 'w', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)

# Konzol handler létrehozása
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(console_formatter)

# Root logger konfigurálása
logger = logging.getLogger('')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def run_script(script_name):
    """
    Futtat egy Python szkriptet és visszaadja a futtatás eredményét
    """
    try:
        logger.info(f"'{script_name}' futtatása kezdődik...")
        
        # A Python interpreter elérési útja
        python_path = sys.executable
        
        # Szkript futtatása
        result = subprocess.run(
            [python_path, script_name],
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"'{script_name}' sikeresen lefutott")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Hiba történt a '{script_name}' futtatása közben:")
        logger.error(f"Hibakód: {e.returncode}")
        logger.error(f"Hibaüzenet: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Váratlan hiba történt a '{script_name}' futtatása közben: {str(e)}")
        return False

def main():
    """
    Fő függvény, ami sorban futtatja a szkripteket
    """
    start_time = datetime.now()
    logger.info("Frissítési folyamat kezdődik...")
    
    # Futtatandó szkriptek listája
    scripts = [
        '02fixtures.py',
        '03oddmapping.py',
        '05updateadom.py',
        '06missing_fixtures.py'
    ]
    
    # Szkriptek futtatása sorban
    success = True
    for script in scripts:
        if not run_script(script):
            logger.error(f"A folyamat megszakadt a '{script}' hibája miatt")
            success = False
            break
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    if success:
        logger.info(f"Minden szkript sikeresen lefutott. Teljes időtartam: {duration}")
    else:
        logger.error(f"A folyamat hibával fejeződött be. Eltelt idő: {duration}")

if __name__ == '__main__':
    main()
