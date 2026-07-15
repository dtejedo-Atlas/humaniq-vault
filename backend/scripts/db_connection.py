"""Conexión a DB para scripts de utilidad. USA LA MISMA LÓGICA QUE server.py (ATLAS_URI > MONGO_URL)."""
import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent.parent / '.env')


def get_db():
    mongo_url = os.environ.get('ATLAS_URI') or os.environ.get('MONGO_URL')
    if not mongo_url:
        raise ValueError("Set ATLAS_URI or MONGO_URL")
    if os.environ.get('ATLAS_URI') and os.environ.get('ATLAS_DB_NAME'):
        db_name = os.environ['ATLAS_DB_NAME']
    else:
        db_name = os.environ['DB_NAME']
    client = MongoClient(mongo_url)
    print(f"[db_connection] Conectado a: {'ATLAS' if os.environ.get('ATLAS_URI') else 'LOCAL'} / db={db_name}")
    return client[db_name]
