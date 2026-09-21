"""Shared database configuration for development migrations."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]


def database_engine():
    load_dotenv(ROOT / '.env')
    raw_url = os.getenv('DATABASE_URL')
    if raw_url:
        url = make_url(raw_url)
        if url.get_backend_name() not in ('postgres', 'postgresql'):
            raise ValueError('DATABASE_URL must point to PostgreSQL')
        url = url.set(drivername='postgresql+psycopg')
    else:
        url = URL.create(
            'postgresql+psycopg',
            username=os.environ['POSTGRES_USER'],
            password=os.environ['POSTGRES_PASSWORD'],
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            database=os.environ['POSTGRES_DB'],
        )
    return create_engine(url, hide_parameters=True)
