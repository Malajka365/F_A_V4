from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime
import math
import logging
import json
from matchespercentage import matches_percentage
from matchespercentageplus import matches_percentage as matches_percentage_plus

# Logging beállítása
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(matches_percentage)
app.register_blueprint(matches_percentage_plus, url_prefix='/plus')

def get_db_connection():
    try:
        conn = sqlite3.connect('football.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Adatbázis kapcsolódási hiba: {str(e)}")
        raise

@app.route('/api/matches')
def get_matches():
    try:
        # Request paraméterek logolása
        logger.debug(f"Beérkezett kérés paraméterek: {request.args}")
        
        # DataTables által küldött paraméterek
        draw = request.args.get('draw', type=int)
        start = request.args.get('start', type=int, default=0)
        length = request.args.get('length', type=int, default=25)

        # Jövőbeli mérkőzések szűrése
        future_only = request.args.get('future_only', type=str) == 'true'
        current_timestamp = int(datetime.now().timestamp())
        
        logger.debug(f"Jövőbeli mérkőzések szűrése: {future_only}")
        logger.debug(f"Jelenlegi időbélyeg: {current_timestamp}")

        # Rendezési paraméterek
        order_column = request.args.get('order[0][column]', type=int, default=0)
        order_dir = request.args.get('order[0][dir]', default='desc')

        # Oszlopok megfeleltetése
        columns = {
            0: 'f.date',
            1: 'f.league_name',
            2: 'f.league_country',
            3: 'f.home_team_name',
            4: "CAST(f.goals_home AS TEXT) || '-' || CAST(f.goals_away AS TEXT)",
            5: 'f.away_team_name',
            6: 'COALESCE(m.home_pr, 0)',
            7: 'COALESCE(m.away_pr, 0)',
            8: 'COALESCE(m.pr_diff, 0)',
            9: '(SELECT odd FROM alldownloadoddmapping WHERE fixture_id = f.id AND bookmaker_name = "Bet365" AND bet_value = "Home" LIMIT 1)',
            10: '(SELECT odd FROM alldownloadoddmapping WHERE fixture_id = f.id AND bookmaker_name = "Bet365" AND bet_value = "Draw" LIMIT 1)',
            11: '(SELECT odd FROM alldownloadoddmapping WHERE fixture_id = f.id AND bookmaker_name = "Bet365" AND bet_value = "Away" LIMIT 1)'
        }

        # Rendezési oszlop kiválasztása
        order_by = columns.get(order_column, 'f.date')
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # Keresési feltételek összeállítása
        search_conditions = []
        params = []

        # Jövőbeli mérkőzések szűrése
        if future_only:
            search_conditions.append('CAST(strftime("%s", f.date) AS INTEGER) >= ?')
            params.append(current_timestamp)
            logger.debug("Jövőbeli mérkőzések szűrési feltétel hozzáadva")

        # Oszloponkénti szűrés
        for i in range(len(columns)):
            column_search = request.args.get(f'columns[{i}][search][value]', '').strip()
            if column_search:
                logger.debug(f"Szűrés a(z) {i}. oszlopra: {column_search}")
                
                if i == 4:  # Eredmény oszlop
                    score_parts = column_search.replace(' ', '').split('-')
                    if len(score_parts) == 2:
                        if score_parts[0].isdigit() and score_parts[1].isdigit():
                            search_conditions.append('(f.goals_home = ? AND f.goals_away = ?)')
                            params.extend([int(score_parts[0]), int(score_parts[1])])
                        elif score_parts[0].isdigit():
                            search_conditions.append('f.goals_home = ?')
                            params.append(int(score_parts[0]))
                        elif score_parts[1].isdigit():
                            search_conditions.append('f.goals_away = ?')
                            params.append(int(score_parts[1]))
                    elif column_search.isdigit():
                        search_conditions.append('(f.goals_home = ? OR f.goals_away = ?)')
                        params.extend([int(column_search), int(column_search)])
                elif i in [6, 7, 8]:  # PR értékek
                    try:
                        pr_value = float(column_search)
                        column = columns[i].replace('COALESCE(', '').split(',')[0]
                        search_conditions.append(f'{column} = ?')
                        params.append(pr_value)
                    except ValueError:
                        continue
                elif i in [9, 10, 11]:  # Odds értékek
                    try:
                        odd_value = float(column_search)
                        search_conditions.append(f'({columns[i]}) = ?')
                        params.append(odd_value)
                    except ValueError:
                        continue
                else:
                    column = columns.get(i)
                    if column:
                        search_conditions.append(f'LOWER({column}) LIKE LOWER(?)')
                        params.append(f"%{column_search}%")

        # WHERE feltétel összeállítása
        where_clause = ''
        if search_conditions:
            where_clause = 'WHERE ' + ' AND '.join(search_conditions)
            logger.debug(f"WHERE feltétel: {where_clause}")
            logger.debug(f"Paraméterek: {params}")

        # Összes rekord számának lekérdezése
        count_query = '''
            SELECT COUNT(*) 
            FROM fixtures f
            LEFT JOIN match_pr_data_this_season m ON f.id = m.fixture_id
        '''
        
        if where_clause:
            count_query += ' ' + where_clause

        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
        filtered_records = total_records

        # Adatok lekérdezése
        query = f'''SELECT 
            f.id,
            f.date,
            f.league_name,
            f.league_country,
            f.home_team_name,
            f.goals_home,
            f.goals_away,
            f.away_team_name,
            COALESCE(m.home_pr, 0) as home_pr,
            COALESCE(m.away_pr, 0) as away_pr,
            COALESCE(m.pr_diff, 0) as pr_diff,
            (SELECT odd FROM alldownloadoddmapping WHERE fixture_id = f.id AND bookmaker_name = "Bet365" AND bet_value = "Home" LIMIT 1) as home_odd,
            (SELECT odd FROM alldownloadoddmapping WHERE fixture_id = f.id AND bookmaker_name = "Bet365" AND bet_value = "Draw" LIMIT 1) as draw_odd,
            (SELECT odd FROM alldownloadoddmapping WHERE fixture_id = f.id AND bookmaker_name = "Bet365" AND bet_value = "Away" LIMIT 1) as away_odd
        FROM fixtures f
        LEFT JOIN match_pr_data_this_season m ON f.id = m.fixture_id
        {where_clause}
        ORDER BY {order_by} {order_dir}
        LIMIT ? OFFSET ?'''

        logger.debug(f"Végső lekérdezés: {query}")
        cursor.execute(query, params + [length, start])
        matches = cursor.fetchall()

        # Odds adatok lekérdezése
        match_data = []
        for match in matches:
            fixture_id = match['id']
            
            # Dátum formázása
            match_dict = dict(match)
            try:
                match_dict['date'] = datetime.fromisoformat(match['date']).strftime('%Y-%m-%d %H:%M')
            except:
                match_dict['date'] = match['date']
            
            # Odds adatok lekérdezése az alldownloadoddmapping táblából
            cursor.execute('''
                SELECT 
                    bookmaker_id,
                    bookmaker_name,
                    bet_value,
                    odd,
                    update_time,
                    fixture_timestamp
                FROM alldownloadoddmapping 
                WHERE fixture_id = ?
                ORDER BY bookmaker_name, bet_value
            ''', (fixture_id,))
            odds = cursor.fetchall()
            
            odds_list = []
            for odd in odds:
                odds_list.append({
                    'bookmaker_id': odd['bookmaker_id'],
                    'bookmaker_name': odd['bookmaker_name'],
                    'bet_value': odd['bet_value'],
                    'odd': float(odd['odd']),
                    'update_time': odd['update_time'],
                    'fixture_timestamp': odd['fixture_timestamp'],
                    'fixture_id': fixture_id
                })

            match_dict['odds'] = odds_list
            match_data.append(match_dict)

        response = {
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': filtered_records,
            'data': match_data
        }

        logger.debug(f"Első mérkőzés odds adatai: {match_data[0]['odds'] if match_data else 'Nincs adat'}")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Hiba történt: {str(e)}")
        return jsonify({
            'error': str(e),
            'draw': draw if 'draw' in locals() else None,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': []
        }), 500

@app.route('/api/odds_history')
def get_odds_history():
    try:
        fixture_id = request.args.get('fixture_id')
        bookmaker_name = request.args.get('bookmaker_name')
        
        if not fixture_id or not bookmaker_name:
            return jsonify({'error': 'Hiányzó paraméterek'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Először lekérjük a bookmaker_id-t a név alapján
        cursor.execute('''
            SELECT DISTINCT bookmaker_id 
            FROM alldownloadoddmapping 
            WHERE bookmaker_name = ?
        ''', (bookmaker_name,))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Nem található fogadóiroda'}), 404
            
        bookmaker_id = result['bookmaker_id']
        
        # Odds történet lekérdezése az alldownloadoddmapping táblából
        cursor.execute('''
            SELECT DISTINCT
                CAST(strftime('%s', update_time) AS INTEGER) as timestamp,
                bet_value,
                odd,
                'current' as source
            FROM alldownloadoddmapping
            WHERE fixture_id = ?
            AND bookmaker_id = ?
            AND bet_value IN ('Home', 'Draw', 'Away')
            ORDER BY timestamp ASC
        ''', (fixture_id, bookmaker_id))
        
        current_odds = cursor.fetchall()
        
        # Odds történet lekérdezése az odds_history táblából
        cursor.execute('''
            SELECT DISTINCT
                CAST(strftime('%s', update_time) AS INTEGER) as timestamp,
                bet_value,
                odd,
                'history' as source
            FROM odds_history
            WHERE fixture_id = ?
            AND bookmaker_id = ?
            AND bet_value IN ('Home', 'Draw', 'Away')
            ORDER BY timestamp ASC
        ''', (fixture_id, bookmaker_id))
        
        history_odds = cursor.fetchall()
        
        # Adatok összefűzése és rendezése típus szerint
        odds_by_type = {
            'Home': [],
            'Draw': [],
            'Away': []
        }
        
        # Aktuális odds-ok feldolgozása
        for odd in current_odds:
            bet_type = odd['bet_value']
            if bet_type in odds_by_type:
                odds_by_type[bet_type].append({
                    'update_time': odd['timestamp'],
                    'odd': float(odd['odd']),
                    'source': odd['source']
                })
        
        # Történeti odds-ok feldolgozása
        for odd in history_odds:
            bet_type = odd['bet_value']
            if bet_type in odds_by_type:
                odds_by_type[bet_type].append({
                    'update_time': odd['timestamp'],
                    'odd': float(odd['odd']),
                    'source': odd['source']
                })
        
        # Rendezés időbélyeg szerint minden típusnál
        for bet_type in odds_by_type:
            odds_by_type[bet_type].sort(key=lambda x: x['update_time'])
        
        logger.debug(f"Odds történet: {sum(len(odds) for odds in odds_by_type.values())} rekord")
        logger.debug(f"Home: {len(odds_by_type['Home'])}, Draw: {len(odds_by_type['Draw'])}, Away: {len(odds_by_type['Away'])}")
        
        return jsonify(odds_by_type)
        
    except Exception as e:
        logger.error(f"Hiba az odds történet lekérdezésekor: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pr-helper-matches')
def get_pr_helper_matches():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        bet_type = request.args.get('type', '')  # home, draw, vagy away
        pr_diff = request.args.get('pr_diff', type=float)
        odd_value = request.args.get('odd_value', type=float)

        if not bet_type or pr_diff is None or odd_value is None:
            return jsonify({'error': 'Hiányzó paraméterek'}), 400

        # Megfelelő tábla kiválasztása
        if bet_type == 'home':
            table = 'pr_helper_home_matches_this_season'
            stats_table = 'pr_helper_home_odd_this_season'
        elif bet_type == 'draw':
            table = 'pr_helper_draw_matches_this_season'
            stats_table = 'pr_helper_draw_odd_this_season'
        elif bet_type == 'away':
            table = 'pr_helper_away_matches_this_season'
            stats_table = 'pr_helper_away_odd_this_season'
        else:
            return jsonify({'error': 'Érvénytelen típus'}), 400

        # Mérkőzések lekérése
        cursor.execute(f'''
            SELECT 
                m.*,
                h.odd as home_odd,
                d.odd as draw_odd,
                a.odd as away_odd
            FROM {table} m
            JOIN {stats_table} s ON m.stat_id = s.id
            LEFT JOIN alldownloadoddmapping h ON m.fixture_id = h.fixture_id 
                AND h.bookmaker_id = '11' AND h.bet_value = 'Home'
            LEFT JOIN alldownloadoddmapping d ON m.fixture_id = d.fixture_id 
                AND d.bookmaker_id = '11' AND d.bet_value = 'Draw'
            LEFT JOIN alldownloadoddmapping a ON m.fixture_id = a.fixture_id 
                AND a.bookmaker_id = '11' AND a.bet_value = 'Away'
            WHERE s.pr_diff = ? AND s.odd_value = ?
            ORDER BY m.date DESC
        ''', (pr_diff, odd_value))

        matches = []
        for row in cursor.fetchall():
            matches.append({
                'fixture_id': row[1],
                'date': row[2],
                'home_team': row[3],
                'away_team': row[4],
                'score': row[5],
                'pr_diff': row[6],
                'odd_value': row[7],
                'home_odd': row[8],
                'draw_odd': row[9],
                'away_odd': row[10]
            })

        return jsonify({'matches': matches})

    except Exception as e:
        logger.error(f"Hiba a mérkőzések lekérésekor: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/pr_helper_this_season')
def pr_helper_this_season():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # PR különbségek statisztikáinak lekérése
        cursor.execute('''
            SELECT 
                pr_diff,
                total_matches,
                home_wins,
                draws,
                away_wins,
                home_win_percentage,
                draw_percentage,
                away_win_percentage
            FROM pr_helper_this_season
            ORDER BY pr_diff
        ''')
        pr_data = [dict(zip([
            'pr_diff', 'total_matches', 'home_wins', 'draws', 'away_wins',
            'home_win_percentage', 'draw_percentage', 'away_win_percentage'
        ], row)) for row in cursor.fetchall()]
        
        # Összes mérkőzés számának lekérése
        cursor.execute('SELECT COUNT(*) FROM pr_helper_this_season')
        total_matches = cursor.fetchone()[0] or 0

        return render_template('pr_helper_this_season.html', pr_data=pr_data, total_matches=total_matches)
    
    except Exception as e:
        logger.error(f"Hiba a PR helper (this season) oldal betöltésekor: {str(e)}")
        return "Hiba történt az oldal betöltésekor", 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/get_matches_by_pr_diff_this_season')
def get_matches_by_pr_diff_this_season():
    try:
        pr_diff = request.args.get('pr_diff', type=float)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Mérkőzések lekérése adott PR különbséghez
        cursor.execute('''
            SELECT 
                f.date,
                f.home_team_name,
                f.away_team_name,
                f.goals_home,
                f.goals_away,
                m.pr_diff,
                h.odd as home_odd,
                d.odd as draw_odd,
                a.odd as away_odd
            FROM match_pr_data_this_season m
            JOIN fixtures f ON m.fixture_id = f.id
            LEFT JOIN alldownloadoddmapping h ON f.id = h.fixture_id 
                AND h.bookmaker_id = '11' AND h.bet_value = 'Home'
            LEFT JOIN alldownloadoddmapping d ON f.id = d.fixture_id 
                AND d.bookmaker_id = '11' AND d.bet_value = 'Draw'
            LEFT JOIN alldownloadoddmapping a ON f.id = a.fixture_id 
                AND a.bookmaker_id = '11' AND a.bet_value = 'Away'
            WHERE ROUND(m.pr_diff, 1) = ?
            AND f.goals_home IS NOT NULL
            AND f.goals_away IS NOT NULL
            AND m.include_in_stats = 1
            ORDER BY f.date DESC
        ''', (pr_diff,))
        
        matches = [{
            'date': row[0],
            'home_team': row[1],
            'away_team': row[2],
            'goals_home': row[3],
            'goals_away': row[4],
            'pr_diff': row[5],
            'home_odd': row[6],
            'draw_odd': row[7],
            'away_odd': row[8]
        } for row in cursor.fetchall()]
        
        return jsonify(matches)
    
    except Exception as e:
        logger.error(f"Hiba a mérkőzések lekérésekor (this season): {str(e)}")
        return jsonify({'error': 'Hiba történt a mérkőzések lekérésekor'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/pr-helper')
def pr_helper():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Home adatok lekérése
        cursor.execute('''
            SELECT pr_diff, odd_value, total_matches, win_count, lose_count, win_percentage, lose_percentage 
            FROM pr_helper_home_odd_this_season 
            ORDER BY pr_diff
        ''')
        home_data = cursor.fetchall()
        cursor.execute('SELECT SUM(total_matches) FROM pr_helper_home_odd_this_season')
        home_total_matches = cursor.fetchone()[0] or 0

        # Draw adatok lekérése
        cursor.execute('''
            SELECT pr_diff, odd_value, total_matches, win_count, lose_count, win_percentage, lose_percentage 
            FROM pr_helper_draw_odd_this_season 
            ORDER BY pr_diff
        ''')
        draw_data = cursor.fetchall()
        cursor.execute('SELECT SUM(total_matches) FROM pr_helper_draw_odd_this_season')
        draw_total_matches = cursor.fetchone()[0] or 0

        # Away adatok lekérése
        cursor.execute('''
            SELECT pr_diff, odd_value, total_matches, win_count, lose_count, win_percentage, lose_percentage 
            FROM pr_helper_away_odd_this_season 
            ORDER BY pr_diff
        ''')
        away_data = cursor.fetchall()
        cursor.execute('SELECT SUM(total_matches) FROM pr_helper_away_odd_this_season')
        away_total_matches = cursor.fetchone()[0] or 0

        return render_template('pr_helper.html', 
                             home_data=home_data,
                             draw_data=draw_data,
                             away_data=away_data,
                             home_total_matches=home_total_matches,
                             draw_total_matches=draw_total_matches,
                             away_total_matches=away_total_matches)
    except Exception as e:
        logger.error(f"Hiba a PR helper adatok lekérésekor: {str(e)}")
        return "Hiba történt az adatok lekérésekor", 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/pr-helper-all')
def pr_helper_all():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # PR különbségek és statisztikák lekérése
        cursor.execute('''
            SELECT 
                pr_diff,
                total_matches,
                home_wins,
                draws,
                away_wins,
                home_win_percentage,
                draw_percentage,
                away_win_percentage
            FROM pr_helper
            ORDER BY pr_diff
        ''')
        pr_data = [dict(row) for row in cursor.fetchall()]
        
        # Összes meccs számának lekérése
        cursor.execute('SELECT SUM(total_matches) FROM pr_helper')
        total_matches = cursor.fetchone()[0] or 0

        return render_template('pr_helper_all.html', 
                             pr_data=pr_data,
                             total_matches=total_matches)
    except Exception as e:
        logger.error(f"Hiba a PR helper (all) adatok lekérésekor: {str(e)}")
        return "Hiba történt az adatok lekérésekor", 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/get_matches', methods=['POST'])
def get_matches_by_pr_diff():
    try:
        pr_diff = request.form.get('pr_diff')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                f.date,
                f.home_team_name,
                f.away_team_name,
                f.goals_home || '-' || f.goals_away as score,
                m.pr_diff
            FROM fixtures f
            JOIN match_pr_data m ON f.id = m.fixture_id
            WHERE ROUND(m.pr_diff, 1) = ?
            ORDER BY f.date DESC
        ''', (pr_diff,))
        
        matches = [dict(row) for row in cursor.fetchall()]
        
        return jsonify({'matches': matches})
    except Exception as e:
        logger.error(f"Hiba a mérkőzések lekérésekor: {str(e)}")
        return jsonify({'error': 'Hiba történt az adatok lekérésekor'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/nezzuk')
def merkozes_analizis():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            f.date AS datum,
            f.league_name AS liga_nev,
            f.league_country AS liga_orszag,
            f.home_team_name AS hazai_csapat,
            f.away_team_name AS vendeg_csapat,
            f.goals_home AS hazai_gol,
            f.goals_away AS vendeg_gol,
            m.pr_diff AS pr_kulonbseg,
            m.home_pr AS hazai_pr,
            m.away_pr AS vendeg_pr,
            (SELECT odd FROM alldownloadoddmapping WHERE fixture_id=f.id AND bet_value='Home' AND bookmaker_name='Bet365' LIMIT 1) AS hazai_odds,
            (SELECT odd FROM alldownloadoddmapping WHERE fixture_id=f.id AND bet_value='Draw' AND bookmaker_name='Bet365' LIMIT 1) AS dontetlen_odds,
            (SELECT odd FROM alldownloadoddmapping WHERE fixture_id=f.id AND bet_value='Away' AND bookmaker_name='Bet365' LIMIT 1) AS vendeg_odds,
            h.total_matches AS hazai_meccsek,
            h.win_percentage AS hazai_szazalek,
            d.total_matches AS dontetlen_meccsek,
            d.win_percentage AS dontetlen_szazalek,
            a.total_matches AS vendeg_meccsek,
            a.win_percentage AS vendeg_szazalek
        FROM fixtures f
        JOIN leagues l ON f.league_id = l.id
        JOIN match_pr_data_this_season m ON f.id = m.fixture_id
        LEFT JOIN pr_helper_home_odd_this_season h ON 
            ROUND(m.pr_diff, 1) = h.pr_diff AND 
            CAST((SELECT odd FROM alldownloadoddmapping WHERE fixture_id=f.id AND bet_value='Home' AND bookmaker_name='Bet365' LIMIT 1) AS TEXT) = h.odd_value
        LEFT JOIN pr_helper_draw_odd_this_season d ON 
            ROUND(m.pr_diff, 1) = d.pr_diff AND 
            CAST((SELECT odd FROM alldownloadoddmapping WHERE fixture_id=f.id AND bet_value='Draw' AND bookmaker_name='Bet365' LIMIT 1) AS TEXT) = d.odd_value
        LEFT JOIN pr_helper_away_odd_this_season a ON 
            ROUND(m.pr_diff, 1) = a.pr_diff AND 
            CAST((SELECT odd FROM alldownloadoddmapping WHERE fixture_id=f.id AND bet_value='Away' AND bookmaker_name='Bet365' LIMIT 1) AS TEXT) = a.odd_value
        WHERE f.goals_home IS NULL AND f.goals_away IS NULL
        ORDER BY f.date DESC
    ''')
    merkozesek = cursor.fetchall()
    conn.close()
    return render_template('nezzuk.html', merkozesek=merkozesek)

@app.route('/matches')
def matches():
    return render_template('matches.html')

@app.route('/matches-percentage')
def matches_percentage():
    return render_template('matchespercentage.html')

@app.route('/matches-percentage-plus')
def matches_percentage_plus():
    return render_template('matchespercentageplus.html')

@app.route('/matches-percentage-data')
def matches_percentage_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # DataTables paraméterek
        draw = request.args.get('draw', type=int)
        start = request.args.get('start', type=int, default=0)
        length = request.args.get('length', type=int, default=25)
        
        # Szűrési paraméterek inicializálása
        filters = []
        filter_values = []
        
        # Dátum szűrő feldolgozása
        date_search = request.args.get('columns[0][search][value]', '')
        if date_search:
            try:
                date_filter = json.loads(date_search)
                if date_filter.get('min'):
                    filters.append("f.date >= ?")
                    filter_values.append(date_filter['min'])
                if date_filter.get('max'):
                    filters.append("f.date <= ?")
                    filter_values.append(date_filter['max'])
            except json.JSONDecodeError:
                print("Hibás dátum szűrő formátum:", date_search)

        # Szöveges szűrők
        text_columns = {
            1: 'f.league_name',
            2: 'f.league_country',
            3: 'f.home_team_name',
            5: 'f.away_team_name'
        }

        for col_idx, db_col in text_columns.items():
            search_value = request.args.get(f'columns[{col_idx}][search][value]', '')
            if search_value:
                filters.append(f"LOWER({db_col}) LIKE LOWER(?)")
                filter_values.append(f"%{search_value}%")

        # Numerikus szűrők
        numeric_columns = {
            6: 'm.home_pr',
            7: 'm.away_pr',
            8: 'm.pr_diff',
            9: 'o.home_odd',
            10: 'o.draw_odd',
            11: 'o.away_odd',
            12: 'h.total_matches',
            13: 'h.win_percentage',
            14: 'd.total_matches',
            15: 'd.win_percentage',
            16: 'a.total_matches',
            17: 'a.win_percentage',
            18: 'p.total_matches',
            19: 'p.home_win_percentage',
            20: 'p.draw_percentage',
            21: 'p.away_win_percentage'
        }

        for col_idx, db_col in numeric_columns.items():
            search_value = request.args.get(f'columns[{col_idx}][search][value]', '')
            if search_value:
                try:
                    num_filter = json.loads(search_value)
                    if num_filter.get('min'):
                        filters.append(f"{db_col} >= ?")
                        filter_values.append(float(num_filter['min']))
                    if num_filter.get('max'):
                        filters.append(f"{db_col} <= ?")
                        filter_values.append(float(num_filter['max']))
                except json.JSONDecodeError:
                    print(f"Hibás numerikus szűrő formátum a {col_idx} oszlopnál:", search_value)

        # Rendezési paraméterek
        order_column_idx = request.args.get('order[0][column]', type=int, default=0)
        order_direction = request.args.get('order[0][dir]', default='desc')
        
        # Oszlopok megfeleltetése a rendezéshez
        columns = {
            0: 'f.date',
            1: 'f.league_name',
            2: 'f.league_country',
            3: 'f.home_team_name',
            4: 'f.goals_home || "-" || f.goals_away',
            5: 'f.away_team_name',
            6: 'm.home_pr',
            7: 'm.away_pr',
            8: 'm.pr_diff',
            9: 'o.home_odd',
            10: 'o.draw_odd',
            11: 'o.away_odd',
            12: 'h.total_matches',
            13: 'h.win_percentage',
            14: 'd.total_matches',
            15: 'd.win_percentage',
            16: 'a.total_matches',
            17: 'a.win_percentage',
            18: 'p.total_matches',
            19: 'p.home_win_percentage',
            20: 'p.draw_percentage',
            21: 'p.away_win_percentage'
        }
        
        order_column = columns.get(order_column_idx, 'f.date')

        # Alap lekérdezés
        base_query = '''
            WITH match_odds AS (
                SELECT 
                    fixture_id,
                    MAX(CASE WHEN bet_value = 'Home' THEN odd END) as home_odd,
                    MAX(CASE WHEN bet_value = 'Draw' THEN odd END) as draw_odd,
                    MAX(CASE WHEN bet_value = 'Away' THEN odd END) as away_odd
                FROM alldownloadoddmapping
                WHERE bookmaker_name = 'Bet365'
                GROUP BY fixture_id
            )
            SELECT 
                f.date,
                f.league_name,
                f.league_country,
                f.home_team_name,
                f.goals_home || '-' || f.goals_away as score,
                f.away_team_name,
                m.home_pr,
                m.away_pr,
                m.pr_diff,
                o.home_odd,
                o.draw_odd,
                o.away_odd,
                COALESCE(h.total_matches, 0) as home_total_matches,
                COALESCE(h.win_percentage, 0) as home_win_percentage,
                COALESCE(d.total_matches, 0) as draw_total_matches,
                COALESCE(d.win_percentage, 0) as draw_win_percentage,
                COALESCE(a.total_matches, 0) as away_total_matches,
                COALESCE(a.win_percentage, 0) as away_win_percentage,
                COALESCE(p.total_matches, 0) as total_matches,
                COALESCE(p.home_win_percentage, 0) as total_home_percentage,
                COALESCE(p.draw_percentage, 0) as total_draw_percentage,
                COALESCE(p.away_win_percentage, 0) as total_away_percentage
            FROM fixtures f
            LEFT JOIN match_pr_data_this_season m ON f.id = m.fixture_id
            LEFT JOIN match_odds o ON f.id = o.fixture_id
            LEFT JOIN pr_helper_home_odd_this_season h ON 
                ROUND(m.pr_diff, 1) = h.pr_diff AND 
                CAST(o.home_odd AS TEXT) = h.odd_value
            LEFT JOIN pr_helper_draw_odd_this_season d ON 
                ROUND(m.pr_diff, 1) = d.pr_diff AND 
                CAST(o.draw_odd AS TEXT) = d.odd_value
            LEFT JOIN pr_helper_away_odd_this_season a ON 
                ROUND(m.pr_diff, 1) = a.pr_diff AND 
                CAST(o.away_odd AS TEXT) = a.odd_value
            LEFT JOIN pr_helper p ON 
                ROUND(m.pr_diff, 1) = p.pr_diff
            WHERE m.include_in_stats = 1
        '''

        # Szűrési feltételek hozzáadása
        where_clause = ""
        if filters:
            where_clause = " AND " + " AND ".join(filters)

        # Számoljuk meg az összes rekordot szűrés előtt
        cursor.execute("SELECT COUNT(*) FROM (" + base_query + ") as sub")
        total_records = cursor.fetchone()[0]

        # Számoljuk meg a szűrt rekordokat
        count_query = "SELECT COUNT(*) FROM (" + base_query + ") as sub" + where_clause
        cursor.execute(count_query, filter_values)
        filtered_records = cursor.fetchone()[0]

        # Végső lekérdezés összeállítása
        query = base_query + where_clause + f" ORDER BY {order_column} {order_direction} LIMIT ? OFFSET ?"
        
        # Paraméterek összeállítása
        params = filter_values + [length, start]
        
        # Debug log
        print("Executing query:", query)
        print("Parameters:", params)
        
        # Lekérdezés végrehajtása
        cursor.execute(query, params)
        
        # Eredmények feldolgozása
        data = []
        for row in cursor.fetchall():
            data.append({
                'date': row['date'],
                'league_name': row['league_name'],
                'league_country': row['league_country'],
                'home_team_name': row['home_team_name'],
                'score': row['score'],
                'away_team_name': row['away_team_name'],
                'home_pr': row['home_pr'],
                'away_pr': row['away_pr'],
                'pr_diff': row['pr_diff'],
                'home_odd': row['home_odd'],
                'draw_odd': row['draw_odd'],
                'away_odd': row['away_odd'],
                'home_total_matches': row['home_total_matches'],
                'home_win_percentage': row['home_win_percentage'],
                'draw_total_matches': row['draw_total_matches'],
                'draw_win_percentage': row['draw_win_percentage'],
                'away_total_matches': row['away_total_matches'],
                'away_win_percentage': row['away_win_percentage'],
                'total_matches': row['total_matches'],
                'total_home_percentage': row['total_home_percentage'],
                'total_draw_percentage': row['total_draw_percentage'],
                'total_away_percentage': row['total_away_percentage']
            })

        return jsonify({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': filtered_records,
            'data': data
        })

    except Exception as e:
        print("Hiba történt:", str(e))
        return jsonify({
            'error': str(e),
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': []
        }), 500

    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
