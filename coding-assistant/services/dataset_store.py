

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from config.settings import get_settings


DATASET_TABLE = "dataset"


def _connect() -> sqlite3.Connection:
   
    db_path = get_settings().dataset_db_path
    conn = sqlite3.connect(db_path)
    return conn
   

def initialize_database() -> None:

    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_dataset(df: pd.DataFrame, filename: str) -> dict:
 
    conn = _connect()
    try:
        df.to_sql(DATASET_TABLE, conn, if_exists="replace", index=False)
        conn.execute("INSERT INTO datasets (filename) VALUES (?)", (filename,))
        conn.commit()
    finally:
        conn.close()

    return {"table": DATASET_TABLE, "columns": list(df.columns)}
def get_dataset_info() -> dict:
    conn = _connect()
    try:
        cursor = conn.execute("SELECT * FROM datasets ORDER BY uploaded_at DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return {"id": row[0], "filename": row[1], "uploaded_at": row[2]}
        else:
            return {"message": "No dataset found."}
    finally:
        conn.close()
def get_schema() -> dict:
    conn = _connect()
    try:
        cursor = conn.execute(f"PRAGMA table_info({DATASET_TABLE})")
        columns = [{"name": col[1], "type": col[2]} for col in cursor.fetchall()]
        return {"table": DATASET_TABLE, "columns": columns}
    finally:
        conn.close()


def validate_sql(sql: str) -> str:

    cleaned = sql.strip().rstrip(";").strip()

    if not cleaned:
        raise ValueError("empty SQL query")
    if not cleaned.lower().startswith("select"):
        raise ValueError(f"only SELECT statements are allowed, got: {cleaned!r}")
    if ";" in cleaned:
        raise ValueError("multiple statements are not allowed")

    return cleaned


def execute_sql(sql: str) -> dict:

    conn = _connect()
    try:
        cursor = conn.execute(sql)
        columns = [description[0] for description in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        return {"columns": columns, "rows": rows}
    finally:
        conn.close()