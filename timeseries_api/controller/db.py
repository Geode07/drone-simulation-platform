#db.py
import asyncpg
import psycopg2
from config.load_config import load_simulation_config
import os

CONFIG = load_simulation_config()
DB_CFG = CONFIG.get("database", {})

def get_psycopg_conn(retries=10, delay=2):
    for attempt in range(retries):
        try:
            return psycopg2.connect(
                dbname=DB_CFG.get("name"),
                user=DB_CFG.get("user"),
                password=DB_CFG.get("password"),
                host=DB_CFG.get("host", "localhost"),
                port=int(os.getenv("DB_PORT", "5432"))
            )
        except psycopg2.OperationalError as e:
            print(f"[DB] Connection attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
    raise Exception("Could not connect to TimescaleDB after multiple attempts.")

async def get_asyncpg_conn():
    return await asyncpg.connect(
        user=DB_CFG.get("user"),
        password=DB_CFG.get("password"),
        database=DB_CFG.get("name"),
        host=DB_CFG.get("host", "localhost"),
        port=int(DB_CFG.get("port", 5432)),
    )
    