#!/usr/bin/env python3
"""
Script to inspect SQL Server schema and print table column names.
Helps identify correct column names for queries.
"""
import pyodbc
import os

def get_mssql_connection():
    """Return a new pyodbc connection using Trusted_Connection (Windows Auth)."""
    driver = os.environ.get('MSSQL_DRIVER', 'ODBC Driver 17 for SQL Server')
    server = 'localhost'
    database = 'SisResiduos'
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)

def inspect_table(table_name):
    """Print all columns for a given table."""
    conn = get_mssql_connection()
    cur = conn.cursor()
    
    print(f"\n=== Columns in table: {table_name} ===")
    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ? AND TABLE_CATALOG = ?
        ORDER BY ORDINAL_POSITION
    """, (table_name, 'SisResiduos'))
    
    rows = cur.fetchall()
    for row in rows:
        print(f"  {row[0]:30} {row[1]}")
    
    if not rows:
        print(f"  [No columns found or table does not exist]")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    tables = ['contenedores', 'mediciones', 'sensores', 'tiposresiduos', 'ubicaciones', 'tipossensores']
    print("Inspecting SQL Server schema...")
    for table in tables:
        try:
            inspect_table(table)
        except Exception as e:
            print(f"\n=== Error inspecting {table} ===")
            print(f"  {e}")
    
    print("\n[Done]")
