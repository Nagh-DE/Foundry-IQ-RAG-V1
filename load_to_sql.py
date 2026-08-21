"""
Loads all CSV files from ./csv/ into Azure SQL Database.
Each CSV becomes a table named after the file (e.g. fred_gdp.csv → fred_gdp).
Run: python load_to_sql.py
"""

import getpass
import urllib
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

SERVER   = "sql-server-rag-nagh.database.windows.net"
DATABASE = "sql-db-rag-nagh"
USERNAME = "Nagh@sql-server-rag-nagh"
DRIVER   = "ODBC Driver 18 for SQL Server"

CSV_DIR = Path(__file__).parent / "csv"


def make_engine(password: str):
    params = urllib.parse.quote_plus(
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"UID={USERNAME};"
        f"PWD={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)


def load_csv(engine, csv_path: Path):
    table = csv_path.stem  # filename without .csv
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().upper() for c in df.columns]  # normalise column names
    with engine.begin() as conn:
        df.to_sql(table, conn, if_exists="replace", index=False, chunksize=500)
    print(f"  OK {table:30s}  {len(df):>7,} rows  {len(df.columns)} cols")


def main():
    import os
    password = os.environ.get("SQL_PWD") or getpass.getpass("Azure SQL password: ")
    engine = make_engine(password)

    # quick connection test
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("Connected successfully.\n")

    csv_files = sorted(CSV_DIR.glob("*.csv"))
    print(f"Loading {len(csv_files)} CSV files...\n")
    for path in csv_files:
        load_csv(engine, path)

    print("\nDone. All tables loaded.")


if __name__ == "__main__":
    main()
