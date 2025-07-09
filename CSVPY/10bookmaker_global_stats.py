import sqlite3
import logging
from collections import defaultdict

# Logging beállítása
logging.basicConfig(
    filename='football_api.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

try:
    # Adatbázis kapcsolat létrehozása
    conn = sqlite3.connect('football.db')
    cursor = conn.cursor()

    # Összes egyedi mérkőzés számának lekérdezése
    cursor.execute('SELECT COUNT(DISTINCT fixture_id) FROM alldownloadoddmapping')
    total_fixtures = cursor.fetchone()[0]

    # Fogadóirodák globális statisztikáinak lekérdezése
    cursor.execute('''
    SELECT 
        bookmaker_name,
        COUNT(*) as total_odds,
        COUNT(DISTINCT fixture_id) as covered_fixtures,
        COUNT(DISTINCT league_id) as leagues_covered
    FROM alldownloadoddmapping
    GROUP BY bookmaker_name
    ORDER BY covered_fixtures DESC, total_odds DESC
    ''')

    results = cursor.fetchall()

    # Eredmények kiírása
    print("\nGlobális Fogadóiroda Statisztika")
    print("=" * 120)
    print(f"Összes egyedi mérkőzés az adatbázisban: {total_fixtures}")
    print("=" * 120)
    print(f"{'Fogadóiroda':<20} {'Odds száma':<15} {'Mérkőzések':<15} {'Lefedett ligák':<15} {'Mérkőzés %':<15} {'Odds/Mérkőzés':<15}")
    print("-" * 120)

    for row in results:
        bookmaker_name, total_odds, covered_fixtures, leagues_covered = row
        coverage_percent = (covered_fixtures / total_fixtures) * 100
        odds_per_fixture = total_odds / covered_fixtures if covered_fixtures > 0 else 0

        print(f"{bookmaker_name:<20} {total_odds:<15} {covered_fixtures:<15} {leagues_covered:<15} {coverage_percent:>6.2f}%{' ':>8} {odds_per_fixture:>6.2f}{' ':>8}")

        # Log fájlba írás
        logging.info(f"Fogadóiroda: {bookmaker_name}")
        logging.info(f"  Összes odds: {total_odds}")
        logging.info(f"  Lefedett mérkőzések: {covered_fixtures}")
        logging.info(f"  Lefedett ligák: {leagues_covered}")
        logging.info(f"  Mérkőzés lefedettség: {coverage_percent:.2f}%")
        logging.info(f"  Odds/Mérkőzés arány: {odds_per_fixture:.2f}")

    print("=" * 120)
    print("\nMagyarázat:")
    print("- Odds száma: Az összes odds bejegyzés száma az adott fogadóirodától")
    print("- Mérkőzések: Hány egyedi mérkőzéshez van odds az adott fogadóirodától")
    print("- Lefedett ligák: Hány különböző ligában van jelen a fogadóiroda")
    print("- Mérkőzés %: A fogadóiroda által lefedett mérkőzések aránya az összes mérkőzéshez képest")
    print("- Odds/Mérkőzés: Átlagosan hány odds tartozik egy mérkőzéshez az adott fogadóirodánál")

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
