import sqlite3

def get_schema():
    conn = sqlite3.connect('football.db')
    cursor = conn.cursor()
    
    # Get all tables
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    
    for table in tables:
        table_name = table[0]
        print(f"\nTábla: {table_name}")
        
        # Get columns for each table
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        for col in columns:
            name, type = col[1], col[2]
            print(f"- {name} ({type})")
    
    conn.close()

if __name__ == "__main__":
    get_schema()
