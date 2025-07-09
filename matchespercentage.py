from flask import Blueprint, render_template, request, jsonify
import sqlite3
import json
import logging
from datetime import datetime

# Blueprint létrehozása
matches_percentage = Blueprint('matches_percentage', __name__)

# Logging beállítása
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Adatbázis kapcsolat létrehozása"""
    try:
        conn = sqlite3.connect('football.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Adatbázis kapcsolódási hiba: {str(e)}")
        raise

def process_numeric_filter(search_value, db_col, col_type):
    try:
        # Vessző csere pontra
        if isinstance(search_value, str):
            search_value = search_value.replace(',', '.')
        
        filter_data = json.loads(search_value)
        filters = []
        values = []
        
        # Minimum érték kezelése
        if 'min' in filter_data and filter_data['min'] is not None:
            min_val = str(filter_data['min']).replace(',', '.')
            filters.append(f"ROUND(CAST({db_col} AS REAL), 2) >= ?")
            values.append(round(float(min_val), 2))
            
        # Maximum érték kezelése
        if 'max' in filter_data and filter_data['max'] is not None:
            max_val = str(filter_data['max']).replace(',', '.')
            filters.append(f"ROUND(CAST({db_col} AS REAL), 2) <= ?")
            values.append(round(float(max_val), 2))
        
        return filters, values
    except Exception as e:
        print(f"Hiba a szűrő feldolgozásában: {str(e)}")
        return [], []

@matches_percentage.route('/matches-percentage')
def show_matches_percentage():
    """Mérkőzés százalékok oldal megjelenítése"""
    return render_template('matchespercentage.html')

@matches_percentage.route('/matches-percentage-data')
def get_matches_percentage_data():
    """Mérkőzés százalékok adatainak lekérése"""
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
        
        # Debug log
        logger.debug("Kapott kérés paraméterek:")
        for key, value in request.args.items():
            logger.debug(f"{key}: {value}")
        
        # Engedélyezett oszlopok
        allowed_columns = {
            1: 'f.league_name',
            2: 'f.league_country',
            3: 'f.home_team_name',
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
        
        # Dátum szűrő feldolgozása
        date_search = request.args.get('columns[0][search][value]', '')
        if date_search:
            try:
                date_filter = json.loads(date_search)
                if date_filter.get('min'):
                    filters.append("STRFTIME('%Y-%m-%d', f.date) >= ?")
                    filter_values.append(date_filter['min'].split('T')[0])
                if date_filter.get('max'):
                    filters.append("STRFTIME('%Y-%m-%d', f.date) <= ?")
                    filter_values.append(date_filter['max'].split('T')[0])
            except json.JSONDecodeError as e:
                logger.debug(f"Nem JSON dátum szűrő: {date_search}")

        # Szöveges szűrők
        text_columns = {1: 'f.league_name', 2: 'f.league_country', 
                       3: 'f.home_team_name', 5: 'f.away_team_name'}
        
        for col_idx, db_col in text_columns.items():
            search_value = request.args.get(f'columns[{col_idx}][search][value]', '').strip()
            if search_value:
                try:
                    # Próbáljuk JSON-ként értelmezni
                    json_filter = json.loads(search_value)
                    if isinstance(json_filter, dict) and 'value' in json_filter:
                        search_value = json_filter['value']
                except json.JSONDecodeError:
                    # Ha nem JSON, használjuk az eredeti értéket
                    pass
                
                if search_value:
                    filters.append(f"LOWER({db_col}) LIKE LOWER(?)")
                    filter_values.append(f"%{search_value}%")

        # Numerikus szűrők feldolgozása
        numeric_columns = {
            6: ('m.home_pr', 'REAL'),  # Hazai PR
            7: ('m.away_pr', 'REAL'),  # Vendég PR
            8: ('m.pr_diff', 'REAL'),   # PR Diff
            9: ('o.home_odd', 'REAL'),  # Hazai Odds
            10: ('o.draw_odd', 'REAL'), # Döntetlen Odds
            11: ('o.away_odd', 'REAL'), # Vendég Odds
            12: ('h.total_matches', 'INTEGER'),  # Hazai Meccsek
            13: ('h.win_percentage', 'REAL'),    # Hazai %
            14: ('d.total_matches', 'INTEGER'),  # Döntetlen Meccsek
            15: ('d.win_percentage', 'REAL'),    # Döntetlen %
            16: ('a.total_matches', 'INTEGER'),  # Vendég Meccsek
            17: ('a.win_percentage', 'REAL'),    # Vendég %
            18: ('p.total_matches', 'INTEGER'),  # Összes Meccs
            19: ('p.home_win_percentage', 'REAL'),  # Összes Hazai %
            20: ('p.draw_percentage', 'REAL'),      # Összes Döntetlen %
            21: ('p.away_win_percentage', 'REAL')   # Összes Vendég %
        }

        for col_idx, (db_col, col_type) in numeric_columns.items():
            search_value = request.args.get(f'columns[{col_idx}][search][value]', '').strip()
            if search_value:
                new_filters, new_values = process_numeric_filter(search_value, db_col, col_type)
                filters.extend(new_filters)
                filter_values.extend(new_values)
                
                # Debug log
                logger.debug(f"Numerikus szűrő feldolgozva: oszlop={col_idx}, érték={search_value}")
                logger.debug(f"Generált szűrők: {new_filters}")
                logger.debug(f"Generált értékek: {new_values}")

        # Alap lekérdezés
        base_query = '''
            WITH match_odds AS (
                SELECT 
                    fixture_id,
                    MAX(CASE WHEN bet_value = 'Home' AND bookmaker_name = 'Bet365' THEN odd END) as home_odd,
                    MAX(CASE WHEN bet_value = 'Draw' AND bookmaker_name = 'Bet365' THEN odd END) as draw_odd,
                    MAX(CASE WHEN bet_value = 'Away' AND bookmaker_name = 'Bet365' THEN odd END) as away_odd
                FROM alldownloadoddmapping
                GROUP BY fixture_id
            )
            SELECT 
                f.date,
                f.league_name,
                f.league_country,
                f.home_team_name,
                f.goals_home || ' - ' || f.goals_away as score,
                f.away_team_name,
                COALESCE(m.home_pr, 0) as home_pr,
                COALESCE(m.away_pr, 0) as away_pr,
                COALESCE(m.pr_diff, 0) as pr_diff,
                COALESCE(o.home_odd, 0) as home_odd,
                COALESCE(o.draw_odd, 0) as draw_odd,
                COALESCE(o.away_odd, 0) as away_odd,
                COALESCE(h.total_matches, 0) as home_total_matches,
                COALESCE(h.win_percentage, 0) as home_win_percentage,
                COALESCE(d.total_matches, 0) as draw_total_matches,
                COALESCE(d.win_percentage, 0) as draw_win_percentage,
                COALESCE(a.total_matches, 0) as away_total_matches,
                COALESCE(a.win_percentage, 0) as away_win_percentage,
                COALESCE(p.total_matches, 0) as total_matches,
                COALESCE(p.home_win_percentage, 0) as total_home_percentage,
                COALESCE(p.draw_percentage, 0) as total_draw_percentage,
                COALESCE(p.away_win_percentage, 0) as total_away_percentage,
                COALESCE(o.home_odd, 0) as calc_home_odd_for_diff,
                COALESCE(o.draw_odd, 0) as calc_draw_odd_for_diff,
                COALESCE(o.away_odd, 0) as calc_away_odd_for_diff
            FROM fixtures f
            LEFT JOIN match_pr_data_this_season m ON f.id = m.fixture_id
            LEFT JOIN match_odds o ON f.id = o.fixture_id
            LEFT JOIN pr_helper_home_odd_this_season h ON 
                ROUND(COALESCE(m.pr_diff, 0), 1) = h.pr_diff AND 
                CAST(COALESCE(o.home_odd, 0) AS TEXT) = h.odd_value
            LEFT JOIN pr_helper_draw_odd_this_season d ON 
                ROUND(COALESCE(m.pr_diff, 0), 1) = d.pr_diff AND 
                CAST(COALESCE(o.draw_odd, 0) AS TEXT) = d.odd_value
            LEFT JOIN pr_helper_away_odd_this_season a ON 
                ROUND(COALESCE(m.pr_diff, 0), 1) = a.pr_diff AND 
                CAST(COALESCE(o.away_odd, 0) AS TEXT) = a.odd_value
            LEFT JOIN pr_helper_this_season p ON 
                ROUND(COALESCE(m.pr_diff, 0), 1) = p.pr_diff
            WHERE m.include_in_stats = 1
        '''

        # Szűrési feltételek hozzáadása
        where_clause = ""
        if filters:
            where_clause = " AND " + " AND ".join(filters)

        # Rendezési paraméterek
        order_column_idx = request.args.get('order[0][column]', type=int, default=0)
        order_direction = request.args.get('order[0][dir]', default='desc')
        
        edge_columns = {22: 'home_edge', 23: 'draw_edge', 24: 'away_edge'}
        if order_column_idx in edge_columns:
            # Cannot sort in SQL, handle later in Python
            order_clause = ""
        else:
            order_column = allowed_columns.get(order_column_idx, 'f.date')
            order_clause = f" ORDER BY {order_column} {order_direction}"
        
        # Végső lekérdezés összeállítása
        final_query = f"{base_query}{where_clause}{order_clause} LIMIT ? OFFSET ?"
        filter_values.extend([length, start])
        
        # Debug log
        logger.debug(f"Végső SQL lekérdezés: {final_query}")
        logger.debug(f"Paraméterek: {filter_values}")
        
        # Lekérdezés végrehajtása
        cursor.execute(final_query, filter_values)
        data = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            try:
                # Implied probabilities from odds
                implied_home = 100 / row_dict['calc_home_odd_for_diff'] if row_dict['calc_home_odd_for_diff'] else 0
                implied_draw = 100 / row_dict['calc_draw_odd_for_diff'] if row_dict['calc_draw_odd_for_diff'] else 0
                implied_away = 100 / row_dict['calc_away_odd_for_diff'] if row_dict['calc_away_odd_for_diff'] else 0

                diff_home = round(row_dict.get('home_win_percentage', 0) - implied_home, 2)
                diff_draw = round(row_dict.get('draw_win_percentage', 0) - implied_draw, 2)
                diff_away = round(row_dict.get('away_win_percentage', 0) - implied_away, 2)

                row_dict['home_edge'] = diff_home
                row_dict['draw_edge'] = diff_draw
                row_dict['away_edge'] = diff_away
            except Exception:
                row_dict['home_edge'] = row_dict['draw_edge'] = row_dict['away_edge'] = None

            # Remove helper keys so they don't get sent to client
            for k in ['calc_home_odd_for_diff', 'calc_draw_odd_for_diff', 'calc_away_odd_for_diff']:
                row_dict.pop(k, None)
            data.append(row_dict)

        # If ordering requested on edge columns, sort here
        if order_column_idx in {22,23,24}:
            key = {22: 'home_edge', 23: 'draw_edge', 24: 'away_edge'}[order_column_idx]
            reverse = (order_direction == 'desc')
            # None values should be last regardless of direction
            data.sort(key=lambda x: (x[key] is None, x[key]), reverse=reverse)
        
        # Összes rekord számának lekérdezése
        count_query = f"SELECT COUNT(*) as count FROM ({base_query}{where_clause})"
        cursor.execute(count_query, filter_values[:-2])  # length és offset paraméterek nélkül
        total_filtered = cursor.fetchone()['count']
        
        # Összes rekord száma szűrés nélkül
        cursor.execute("SELECT COUNT(*) as count FROM fixtures f LEFT JOIN match_pr_data_this_season m ON f.id = m.fixture_id WHERE m.include_in_stats = 1")
        total_records = cursor.fetchone()['count']
        
        return jsonify({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': total_filtered,
            'data': data
        })
        
    except Exception as e:
        logger.error(f"Hiba történt: {str(e)}")
        return jsonify({
            'draw': request.args.get('draw', 1),
            'error': f"Hiba a szűrésben: {str(e)}",
            'debug_info': {
                'request_params': dict(request.args),
                'error_type': type(e).__name__
            }
        }), 400
    
    finally:
        if 'conn' in locals():
            conn.close()

@matches_percentage.route('/get-matches-by-stat')
def get_matches_by_stat():
    """Visszaadja a mérkőzéseket egy adott PR különbség és odds érték alapján"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Paraméterek lekérése
        pr_diff = request.args.get('pr_diff', type=float)
        odd_value = request.args.get('odd_value', type=float)
        stat_type = request.args.get('stat_type', type=str)  # 'home', 'draw', 'away'
        
        # Ellenőrizzük, hogy minden szükséges paraméter megvan-e
        if pr_diff is None or odd_value is None or stat_type not in ['home', 'draw', 'away']:
            return jsonify({
                'error': 'Hiányzó vagy érvénytelen paraméterek',
                'required': {
                    'pr_diff': 'float',
                    'odd_value': 'float',
                    'stat_type': 'home, draw vagy away'
                }
            }), 400
        
        # Kerekítés egy tizedesjegyre
        pr_diff_rounded = round(pr_diff, 1)
        odd_value_str = str(odd_value)
        
        # Lekérdezés összeállítása a stat_type alapján
        table_prefix = ''
        if stat_type == 'home':
            table_prefix = 'h'
        elif stat_type == 'draw':
            table_prefix = 'd'
        elif stat_type == 'away':
            table_prefix = 'a'
        
        query = f'''
            SELECT 
                s.fixture_id,
                s.date,
                s.home_team,
                s.away_team,
                s.score,
                s.pr_diff,
                s.odd_value
            FROM pr_helper_{stat_type}_matches_this_season s
            JOIN pr_helper_{stat_type}_odd_this_season t ON s.stat_id = t.id
            WHERE t.pr_diff = ? AND t.odd_value = ?
            ORDER BY s.date DESC
        '''
        
        cursor.execute(query, (pr_diff_rounded, odd_value_str))
        matches = [dict(row) for row in cursor.fetchall()]
        
        # Statisztikai adatok lekérdezése
        stat_query = f'''
            SELECT 
                total_matches,
                win_count,
                lose_count,
                win_percentage,
                lose_percentage
            FROM pr_helper_{stat_type}_odd_this_season
            WHERE pr_diff = ? AND odd_value = ?
        '''
        
        cursor.execute(stat_query, (pr_diff_rounded, odd_value_str))
        stats = dict(cursor.fetchone() or {})
        
        return jsonify({
            'matches': matches,
            'stats': stats,
            'parameters': {
                'pr_diff': pr_diff_rounded,
                'odd_value': odd_value,
                'stat_type': stat_type
            }
        })
        
    except Exception as e:
        logger.error(f"Hiba a mérkőzések lekérdezésénél: {str(e)}")
        return jsonify({
            'error': f"Hiba a mérkőzések lekérdezésénél: {str(e)}"
        }), 500
        
    finally:
        if 'conn' in locals():
            conn.close()
