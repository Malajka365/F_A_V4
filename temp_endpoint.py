@matches_percentage.route('/get-all-bookmaker-odds')
def get_all_bookmaker_odds():
    """Visszaadja az összes fogadóiroda odds értékeit egy adott mérkőzéshez"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Paraméterek lekérése
        fixture_id = request.args.get('fixture_id', type=int)
        bet_type = request.args.get('bet_type', type=str)  # 'Home', 'Draw', 'Away'
        
        # Ellenőrizzük, hogy minden szükséges paraméter megvan-e
        if fixture_id is None or bet_type not in ['Home', 'Draw', 'Away']:
            return jsonify({
                'error': 'Hiányzó vagy érvénytelen paraméterek',
                'required': {
                    'fixture_id': 'int',
                    'bet_type': 'Home, Draw vagy Away'
                }
            }), 400
        
        # Lekérdezés az összes fogadóiroda odds értékeiért
        query = '''
            SELECT 
                bookmaker_name,
                odd,
                update_time
            FROM alldownloadoddmapping
            WHERE fixture_id = ? AND bet_value = ?
            ORDER BY update_time DESC
        '''
        
        cursor.execute(query, (fixture_id, bet_type))
        odds_data = [dict(row) for row in cursor.fetchall()]
        
        # Csoportosítás fogadóirodák szerint és a legfrissebb értékek kiválasztása
        bookmakers = {}
        for odd in odds_data:
            bookmaker = odd['bookmaker_name']
            if bookmaker not in bookmakers:
                bookmakers[bookmaker] = {
                    'bookmaker_name': bookmaker,
                    'odd': odd['odd'],
                    'update_time': odd['update_time']
                }
        
        # Odds értékek időbeli változásának lekérése (grafikonhoz)
        time_query = '''
            SELECT 
                bookmaker_name,
                odd,
                update_time
            FROM odds_history
            WHERE fixture_id = ? AND bet_value = ?
            ORDER BY update_time ASC
        '''
        
        cursor.execute(time_query, (fixture_id, bet_type))
        time_series_data = [dict(row) for row in cursor.fetchall()]
        
        # Csoportosítás fogadóirodák szerint idősorosan
        time_series = {}
        for odd in time_series_data:
            bookmaker = odd['bookmaker_name']
            if bookmaker not in time_series:
                time_series[bookmaker] = []
            
            time_series[bookmaker].append({
                'odd': odd['odd'],
                'update_time': odd['update_time']
            })
        
        # Mérkőzés adatok lekérése
        match_query = '''
            SELECT 
                home_team_name,
                away_team_name,
                date
            FROM fixtures
            WHERE id = ?
        '''
        
        cursor.execute(match_query, (fixture_id,))
        match_data = dict(cursor.fetchone() or {})
        
        return jsonify({
            'current_odds': list(bookmakers.values()),
            'time_series': time_series,
            'match_info': match_data,
            'bet_type': bet_type
        })
        
    except Exception as e:
        logger.error(f"Hiba az odds értékek lekérdezésénél: {str(e)}")
        return jsonify({
            'error': f"Hiba az odds értékek lekérdezésénél: {str(e)}"
        }), 500
        
    finally:
        if 'conn' in locals():
            conn.close()
