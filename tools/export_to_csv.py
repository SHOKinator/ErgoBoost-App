import sqlite3
import pandas as pd
import os
from pathlib import Path

def export_db_to_csv(db_path="data/ergoboost.db", output_dir="data/csv_export"):
    """
    Exports all tables from the SQLite database to CSV files.
    """
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"Error: Database file not found at {db_file.absolute()}")
        return
        
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    if not tables:
        print("No tables found in the database.")
        return
        
    for table_name in tables:
        table_name = table_name[0]
        if table_name == 'sqlite_sequence':
            continue
            
        print(f"Exporting table '{table_name}'...")
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)
        
        csv_path = out_dir / f"{table_name}.csv"
        df.to_csv(csv_path, index=False)
        print(f"  -> Saved {len(df)} rows to {csv_path}")
        
    conn.close()
    print(f"\nAll tables have been exported to {out_dir.absolute()}")

if __name__ == "__main__":
    # Ensure current working directory is the project root
    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent
    os.chdir(project_root)
    
    export_db_to_csv()
