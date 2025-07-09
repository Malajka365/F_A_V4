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

    # Liga statisztikák lekérdezése
    cursor.execute('''
    WITH FixtureCount AS (
        SELECT 
            league_id,
            league_name,
            COUNT(DISTINCT fixture_id) as fixture_count
        FROM alldownloadoddmapping
        GROUP BY league_id, league_name
    ),
    BookmakerStats AS (
        SELECT 
            league_id,
            bookmaker_name,
            COUNT(*) as odds_count,
            COUNT(DISTINCT fixture_id) as fixture_count
        FROM alldownloadoddmapping
        GROUP BY league_id, bookmaker_name
    )
    SELECT 
        f.league_id,
        f.league_name,
        f.fixture_count as total_fixtures,
        b.bookmaker_name,
        b.odds_count,
        b.fixture_count as bookmaker_fixtures
    FROM FixtureCount f
    JOIN BookmakerStats b ON f.league_id = b.league_id
    ORDER BY f.league_id, b.odds_count DESC
    ''')

    results = cursor.fetchall()
    
    # Eredmények rendszerezése
    stats_by_league = defaultdict(lambda: {'name': '', 'total_fixtures': 0, 'bookmakers': []})
    
    for row in results:
        league_id, league_name, total_fixtures, bookmaker_name, odds_count, bookmaker_fixtures = row
        
        if not stats_by_league[league_id]['name']:
            stats_by_league[league_id]['name'] = league_name
            stats_by_league[league_id]['total_fixtures'] = total_fixtures
            
        stats_by_league[league_id]['bookmakers'].append({
            'name': bookmaker_name,
            'odds_count': odds_count,
            'fixture_count': bookmaker_fixtures
        })

    # Eredmények kiírása
    print("\nStatisztika az alldownloadoddmapping tábláról:\n")
    print("=" * 100)
    
    for league_id, data in sorted(stats_by_league.items()):
        print(f"\nLiga ID: {league_id}")
        print(f"Liga név: {data['name']}")
        print(f"Összes mérkőzés: {data['total_fixtures']}")
        print("\nFogadóirodák statisztikája:")
        print("-" * 80)
        print(f"{'Fogadóiroda':<30} {'Odds száma':<15} {'Mérkőzések száma':<20} {'Lefedettség %':<15}")
        print("-" * 80)
        
        for bm in sorted(data['bookmakers'], key=lambda x: x['odds_count'], reverse=True):
            coverage = (bm['fixture_count'] / data['total_fixtures']) * 100 if data['total_fixtures'] > 0 else 0
            print(f"{bm['name']:<30} {bm['odds_count']:<15} {bm['fixture_count']:<20} {coverage:.2f}%")
        
        print("=" * 100)

        # Log fájlba írás
        logging.info(f"Liga statisztika - ID: {league_id}, Név: {data['name']}, Mérkőzések: {data['total_fixtures']}")
        for bm in data['bookmakers']:
            coverage = (bm['fixture_count'] / data['total_fixtures']) * 100 if data['total_fixtures'] > 0 else 0
            logging.info(f"  Fogadóiroda: {bm['name']}, Odds: {bm['odds_count']}, Mérkőzések: {bm['fixture_count']}, Lefedettség: {coverage:.2f}%")

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
