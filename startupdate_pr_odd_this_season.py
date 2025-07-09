import subprocess
import sys
import os
import logging
from datetime import datetime

# Python elérési út beállítása
python_path = sys.executable

# Logolás beállítása
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Log fájl neve időbélyeggel
log_filename = os.path.join(log_dir, f"startupdate_pr_odd_this_season_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Logger beállítása
logger = logging.getLogger('startupdate_pr_odd')
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

def run_script(script_name):
    try:
        logger.info(f"'{script_name}' futtatása kezdődik...")
        result = subprocess.run([python_path, script_name], capture_output=True, text=True, check=True)
        logger.info(f"'{script_name}' sikeresen lefutott")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Hiba történt a '{script_name}' futtatása közben:")
        logger.error(f"Hibaüzenet: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Váratlan hiba történt a '{script_name}' futtatása közben: {str(e)}")
        return False

def main():
    logger.info("Szkript futtatás kezdődik...")
    
    # Szkriptek futtatása sorrendben
    scripts = [
        "pr_calculator_this_season.py",
        "pr_helper_odd_this_season.py"
    ]
    
    for script in scripts:
        if not run_script(script):
            logger.error(f"A folyamat megszakadt a '{script}' hibája miatt")
            sys.exit(1)
    
    logger.info("Minden szkript sikeresen lefutott")

if __name__ == "__main__":
    main()
