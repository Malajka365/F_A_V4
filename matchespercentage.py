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

        # Rendezési paraméterek (SQL-hez, Edge oszlopok nélkül)
        order_column_idx = request.args.get('order[0][column]', type=int, default=0)
        order_direction = request.args.get('order[0][dir]', default='desc')
        
        sql_order_clause = ""
        # Az Edge oszlopokra (22, 23, 24) és a total_away_percentage (21) oszlopra később, Pythonban rendezünk
        # Mivel a total_away_percentage (p.away_win_percentage) már az SQL-ben is létezik,
        # a 21-es oszlopra történő rendezést SQL-ben is meg lehetne tenni, de az egyszerűség kedvéért
        # az összes Pythonban számított/használt oszlopot Pythonban rendezzük.
        edge_column_indices = {21, 22, 23, 24}

        if order_column_idx not in edge_column_indices and order_column_idx in allowed_columns:
            order_column = allowed_columns.get(order_column_idx, 'f.date')
            sql_order_clause = f" ORDER BY {order_column} {order_direction}"
        elif order_column_idx not in edge_column_indices: # Ha nincs explicit SQL rendezés, alapértelmezett
             sql_order_clause = f" ORDER BY f.date {order_direction}"


        # Végső lekérdezés összeállítása (LIMIT és OFFSET nélkül egyelőre)
        # A lapozást a Python oldali szűrés után végezzük el
        final_query = f"{base_query}{where_clause}{sql_order_clause}"
        
        # Debug log
        logger.debug(f"SQL lekérdezés (lapozás előtt): {final_query}")
        logger.debug(f"SQL paraméterek: {filter_values}")
        
        # Lekérdezés végrehajtása
        cursor.execute(final_query, filter_values)
        all_data_from_sql = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            try:
                # Implied probabilities from odds
                implied_home = 100 / row_dict['calc_home_odd_for_diff'] if row_dict['calc_home_odd_for_diff'] and row_dict['calc_home_odd_for_diff'] != 0 else 0
                implied_draw = 100 / row_dict['calc_draw_odd_for_diff'] if row_dict['calc_draw_odd_for_diff'] and row_dict['calc_draw_odd_for_diff'] != 0 else 0
                implied_away = 100 / row_dict['calc_away_odd_for_diff'] if row_dict['calc_away_odd_for_diff'] and row_dict['calc_away_odd_for_diff'] != 0 else 0

                diff_home = round(row_dict.get('home_win_percentage', 0) - implied_home, 2)
                diff_draw = round(row_dict.get('draw_win_percentage', 0) - implied_draw, 2)
                diff_away = round(row_dict.get('away_win_percentage', 0) - implied_away, 2)

                row_dict['home_edge'] = diff_home
                row_dict['draw_edge'] = diff_draw
                row_dict['away_edge'] = diff_away
            except Exception as e_calc:
                logger.error(f"Hiba az Edge értékek számításakor: {str(e_calc)} sor: {row_dict.get('fixture_id', 'N/A')}")
                row_dict['home_edge'] = row_dict['draw_edge'] = row_dict['away_edge'] = None

            # Remove helper keys so they don't get sent to client
            for k in ['calc_home_odd_for_diff', 'calc_draw_odd_for_diff', 'calc_away_odd_for_diff']:
                row_dict.pop(k, None)
            all_data_from_sql.append(row_dict)

        # Python oldali szűrés az Edge% oszlopokra és Összes Vendég %-ra (ha van)
        # Az Összes Vendég % (total_away_percentage) oszlop indexe 21, ami 'p.away_win_percentage' az SQL-ben
        # és 'total_away_percentage' a Python dict-ben.
        # Az Edge oszlopok indexei: home_edge: 22, draw_edge: 23, away_edge: 24

        python_filtered_data = []
        
        # Szűrő paraméterek az Edge oszlopokhoz és total_away_percentage-hez
        edge_filter_params = {}
        # Oszlop indexek a frontendről, és a megfelelő kulcsok a `row_dict`-ben
        python_filterable_columns = {
            21: 'total_away_percentage', # Ez az 'Összes Vendég %'
            22: 'home_edge',
            23: 'draw_edge',
            24: 'away_edge'
        }

        for col_idx, data_key in python_filterable_columns.items():
            search_value_str = request.args.get(f'columns[{col_idx}][search][value]', '').strip()
            if search_value_str:
                try:
                    search_params = json.loads(search_value_str)
                    min_val = search_params.get('min')
                    max_val = search_params.get('max')

                    # Vessző csere pontra és float konverzió
                    if min_val is not None:
                        min_val = float(str(min_val).replace(',', '.'))
                    if max_val is not None:
                        max_val = float(str(max_val).replace(',', '.'))

                    edge_filter_params[data_key] = {'min': min_val, 'max': max_val}
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Érvénytelen JSON vagy érték a(z) {data_key} szűrőhöz: {search_value_str}, hiba: {e}")


        for row_dict in all_data_from_sql:
            match = True
            for data_key, params in edge_filter_params.items():
                value = row_dict.get(data_key)
                if value is None: # Ha az érték None, nem felel meg a min/max szűrőnek (kivéve, ha a szűrő is None)
                    match = False
                    break

                # Kerekítés 2 tizedesjegyre a szűrés előtt, ahogy a process_numeric_filter is teszi
                # Az Edge értékek már kerekítve vannak a számításkor.
                # A total_away_percentage (p.away_win_percentage) is valószínűleg kerekítve van az adatbázisban vagy a rendereléskor.
                # A biztonság kedvéért itt is kerekíthetünk, ha szükséges, de a `value` már a végleges érték.

                if params['min'] is not None and round(value, 2) < round(params['min'], 2):
                    match = False
                    break
                if params['max'] is not None and round(value, 2) > round(params['max'], 2):
                    match = False
                    break

            if match:
                python_filtered_data.append(row_dict)

        total_filtered_after_python = len(python_filtered_data)

        # Rendezés Pythonban, ha a rendezési oszlop az Edge vagy total_away_percentage oszlopok egyike
        # A `order_column_idx` a frontend által küldött oszlopindex
        # `python_filterable_columns` mapolja ezt a `row_dict` kulcsaira
        if order_column_idx in python_filterable_columns:
            sort_key_name = python_filterable_columns[order_column_idx]
            reverse_sort = (order_direction == 'desc')

            # None értékek hátra kerüljenek függetlenül a rendezési iránytól
            python_filtered_data.sort(key=lambda x: (x[sort_key_name] is None, x[sort_key_name]), reverse=reverse_sort)
        elif not sql_order_clause: # Ha nem volt SQL rendezés (mert pl. Edge oszlopra volt, de az üres)
                                   # és a jelenlegi order_column_idx sem Pythonban rendezendő, akkor alapértelmezett dátum szerint.
                                   # Ez a rész már nem feltétlenül szükséges, ha az sql_order_clause mindig beállít egy alap rendezést.
            python_filtered_data.sort(key=lambda x: x.get('date', datetime.min.isoformat()), reverse=(order_direction == 'desc'))


        # Lapozás alkalmazása a Python által szűrt és rendezett adatokra
        paginated_data = python_filtered_data[start : start + length]
        
        # Összes rekord száma szűrés nélkül (ez maradhat, a teljes adatbázisra vonatkozik)
        # Ezt csak egyszer kell lekérdezni, ha még nincs meg.
        # Mivel ez a függvény minden DataTables kérésre lefut, optimalizálható lenne,
        # de a jelenlegi működés szerint hagyjuk.
        if 'total_records' not in locals() or total_records is None: # Csak akkor, ha még nem volt beállítva
            count_query_total = "SELECT COUNT(*) as count FROM fixtures f LEFT JOIN match_pr_data_this_season m ON f.id = m.fixture_id WHERE m.include_in_stats = 1"
            cursor.execute(count_query_total)
            total_records = cursor.fetchone()['count']
        
        return jsonify({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': total_filtered_after_python, # Ez most a Python szűrés utáni szám
            'data': paginated_data
        })
        
    except Exception as e:
        logger.error(f"Hiba történt a matches-percentage-data feldolgozásakor: {str(e)}", exc_info=True)
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
