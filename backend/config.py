"""
Configuration for Flask backend application.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Always load from the project root .env, regardless of CWD.
# backend/config.py → backend/ → web_scraper/ (root)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / '.env')

_secret_key = os.getenv('SECRET_KEY')
if not _secret_key:
    raise RuntimeError("SECRET_KEY environment variable must be set")


class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = _secret_key
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'

    # Database
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 5432))
    DB_NAME = os.getenv('DB_NAME', 'price_scraper')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')

    # Server
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')

    # Pagination
    DEFAULT_PAGE_SIZE = 24
    MAX_PAGE_SIZE = 100

    @classmethod
    def get_database_url(cls):
        """Get PostgreSQL connection string."""
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"

    @classmethod
    def get_db_config(cls):
        """Get database configuration dictionary."""
        return {
            'host': cls.DB_HOST,
            'port': cls.DB_PORT,
            'database': cls.DB_NAME,
            'user': cls.DB_USER,
            'password': cls.DB_PASSWORD
        }
