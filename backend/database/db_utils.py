#!/usr/bin/env python3
"""
Database utilities for web scraper PostgreSQL database.
Handles connections, queries, and common database operations.
"""

import os
import re
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor, execute_values
from contextlib import contextmanager
from typing import List, Dict, Optional, Any, Tuple
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration from environment variables."""

    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = int(os.getenv('DB_PORT', '5432'))
        self.database = os.getenv('DB_NAME', 'price_scraper')
        self.user = os.getenv('DB_USER', 'scraper_app')
        self.password = os.getenv('DB_PASSWORD', '')
        self.min_connections = int(os.getenv('DB_MIN_CONN', '2'))
        self.max_connections = int(os.getenv('DB_MAX_CONN', '10'))

    @property
    def dsn(self) -> str:
        """Get connection string."""
        return f"host={self.host} port={self.port} dbname={self.database} user={self.user} password={self.password}"

    def get_dict(self) -> dict:
        """Get config as dictionary for psycopg2."""
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.user,
            'password': self.password
        }


class Database:
    """Database connection manager with connection pooling."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self._pool = None

    def initialize_pool(self):
        """Initialize connection pool."""
        if self._pool is None:
            try:
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    self.config.min_connections,
                    self.config.max_connections,
                    **self.config.get_dict()
                )
                logger.info("Database connection pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize connection pool: {e}")
                raise

    def close_pool(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("Database connection pool closed")

    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool.

        Usage:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM products")
        """
        if self._pool is None:
            self.initialize_pool()

        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor):
        """
        Get a cursor with automatic connection management.

        Usage:
            with db.get_cursor() as cur:
                cur.execute("SELECT * FROM products")
                results = cur.fetchall()
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()


# Global database instance
_db_instance = None


def get_db() -> Database:
    """Get global database instance (singleton)."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


def extract_volume_ml(title: str) -> Optional[int]:
    """
    Extract volume from title and convert to milliliters.

    Returns:
        Volume in ml, or None if not found

    Examples:
        "Jack Daniel's 0.7l" → 700
        "Vodka 700ml" → 700
        "Whisky 70cl" → 700
        "Gin0.5l" → 500
    """
    title_lower = title.lower()

    # Match volume patterns: 0.7l, 0,7l, 700ml, 70cl, whisky0.7l, etc.
    patterns = [
        # Decimal liters: 0.7l, 0,7l, 1.75l
        (r'(\d+)[,.](\d+)\s*l\b', lambda m: int(m.group(1)) * 1000 + int(m.group(2)) * (100 if len(m.group(2)) == 1 else 10)),
        # Whole liters: 1l, 2l
        (r'(\d+)\s*l\b', lambda m: int(m.group(1)) * 1000),
        # Milliliters: 700ml, 500ml
        (r'(\d+)\s*ml\b', lambda m: int(m.group(1))),
        # Centiliters: 70cl, 75cl
        (r'(\d+)\s*cl\b', lambda m: int(m.group(1)) * 10),
    ]

    for pattern, converter in patterns:
        match = re.search(pattern, title_lower)
        if match:
            return converter(match)

    return None


def normalize_title(title: str) -> str:
    """
    Normalize product title for matching across different sources.

    Handles:
    - Case normalization
    - Volume standardization (0.7l, 0,7 L, 0.70 L → 07l)
    - Age standardization (12YO, 12 yo, 12 years → 12yo)
    - Packaging words removal
    - Brand name standardization
    """
    # Lowercase
    normalized = title.lower()

    # Standardize whisky/whiskey
    normalized = normalized.replace('whiskey', 'whisky')

    # Remove "the" prefix
    normalized = re.sub(r'\bthe\s+', '', normalized)

    # Standardize volume format BEFORE removal
    # Handle all cases: 0.7l, 0,7l, 0.70L, 700ml, whisky0.7l, 12YO0.7l

    # First: Handle attached volumes (no space): whisky0.7l, 12YO0.7l → add space
    normalized = re.sub(r'([a-z])(\d+[,.]?\d*)(l|ml|cl)\b', r'\1 \2\3', normalized)

    # Second: Standardize all volume formats to remove separators
    # 0.7l, 0,7l → 07l | 0.70l → 070l | 700ml → 700ml | 1.0l → 10l
    normalized = re.sub(r'(\d+)[,.](\d+)\s*(l|ml|cl)\b', r'\1\2\3', normalized)

    # Third: Handle simple volumes without decimal: 1l → 1l (keep as is)
    normalized = re.sub(r'(\d+)\s+(l|ml|cl)\b', r'\1\2', normalized)

    # Standardize age indicators (12 YO, 12YO, 12yo, 12 years → 12yo)
    normalized = re.sub(r'(\d+)\s*y\.?o\.?', r'\1yo', normalized)
    normalized = re.sub(r'(\d+)\s*years?\s*old', r'\1yo', normalized)
    normalized = re.sub(r'(\d+)\s*years?', r'\1yo', normalized)

    # Remove packaging/gift related words (but preserve important variant descriptors)
    packaging_words = [
        r'\+\s*gb\b', r'\+\s*karton\b', r'\+\s*čaše', r'\+\s*case',
        r'\+\s*glass', r'\+\s*pack', r'\+\s*box', r'\+\s*cradle',
        r'\+\s*stalak', r'\+\s*\d+\s*čaš[ea]', r'\bkarton\b',
        r'\bcradle\b', r'\bstalak\b', r'\beco\b', r'\bcooler\b',
        r'\bice\s*jacket\b', r'\bfridge\b'
    ]
    for word in packaging_words:
        normalized = re.sub(word, '', normalized)

    # Note: We keep category descriptors (whisky, vodka, gin, etc.) as they help distinguish products
    # We also keep important variant words: gold, platinum, black, reserve, xo, vsop, etc.

    # Remove volume indicators after standardization
    normalized = re.sub(r'\d+(?:\.\d+)?\s*(l|ml|cl)\b', '', normalized)

    # Remove special characters but keep spaces
    normalized = re.sub(r'[^\w\s]', ' ', normalized)

    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized)

    # Trim
    normalized = normalized.strip()

    return normalized


def parse_price(price_str: str) -> Optional[Decimal]:
    """
    Parse price string to Decimal.

    Handles formats:
    - "99,99€"
    - "99.99 €"
    - "3.339,50€" (thousands separator)
    - "99,50"
    - "99.99"
    - "Ponuda na upit" -> None (non-numeric strings)
    """
    if not price_str:
        return None

    try:
        # Check if string contains actual numbers
        if not re.search(r'\d', price_str):
            logger.debug(f"No numeric value in price '{price_str}', treating as unavailable")
            return None

        # Remove currency symbols and whitespace
        cleaned = re.sub(r'[€$\s]', '', price_str)

        # Handle European format with thousands separator (3.339,50 -> 3339.50)
        # If we have both . and , then . is thousands separator
        if '.' in cleaned and ',' in cleaned:
            # Remove thousands separator (.)
            cleaned = cleaned.replace('.', '')
            # Replace decimal separator (,) with dot
            cleaned = cleaned.replace(',', '.')
        # If only comma, it's the decimal separator
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
        # If only dot, assume it's decimal (or thousands - check position)
        # If dot is 3 digits from end, it's likely thousands (e.g., 1.500)

        # Convert to Decimal
        return Decimal(cleaned)

    except Exception as e:
        logger.warning(f"Failed to parse price '{price_str}': {e}")
        return None


class ProductRepository:
    """Repository for product database operations."""

    def __init__(self, db: Database):
        self.db = db

    def get_source_id(self, source_name: str) -> Optional[int]:
        """Get source ID by name."""
        with self.db.get_cursor() as cur:
            cur.execute(
                "SELECT id FROM sources WHERE name = %s",
                (source_name,)
            )
            result = cur.fetchone()
            return result['id'] if result else None

    def get_category_id(self, category_slug: str) -> Optional[int]:
        """Get category ID by slug."""
        with self.db.get_cursor() as cur:
            cur.execute(
                "SELECT id FROM categories WHERE slug = %s",
                (category_slug,)
            )
            result = cur.fetchone()
            return result['id'] if result else None

    def create_or_update_product(
        self,
        source_name: str,
        category_slug: Optional[str],
        title: str,
        price: Decimal,
        product_url: str,
        image_url: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Create new product or update existing one.

        Returns product ID.
        """
        source_id = self.get_source_id(source_name)
        if not source_id:
            raise ValueError(f"Source '{source_name}' not found in database")

        category_id = None
        if category_slug:
            category_id = self.get_category_id(category_slug)

        normalized = normalize_title(title)

        with self.db.get_cursor() as cur:
            # Try to find existing product
            cur.execute(
                """
                SELECT id, price FROM products
                WHERE source_id = %s AND product_url = %s
                """,
                (source_id, product_url)
            )
            existing = cur.fetchone()

            if existing:
                # Update existing product
                cur.execute(
                    """
                    UPDATE products SET
                        category_id = %s,
                        title = %s,
                        normalized_title = %s,
                        price = %s,
                        image_url = %s,
                        metadata = %s,
                        is_available = true,
                        last_seen_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id
                    """,
                    (category_id, title, normalized, price, image_url,
                     psycopg2.extras.Json(metadata) if metadata else None,
                     existing['id'])
                )
                logger.info(f"Updated product ID {existing['id']}: {title}")
                return existing['id']
            else:
                # Insert new product
                cur.execute(
                    """
                    INSERT INTO products (
                        source_id, category_id, title, normalized_title,
                        price, product_url, image_url, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (source_id, category_id, title, normalized, price,
                     product_url, image_url,
                     psycopg2.extras.Json(metadata) if metadata else None)
                )
                product_id = cur.fetchone()['id']
                logger.info(f"Created product ID {product_id}: {title}")
                return product_id

    def bulk_insert_products(
        self,
        products: List[Dict[str, Any]],
        source_name: str,
        category_slug: Optional[str] = None
    ) -> int:
        """
        Bulk insert/update products for better performance.

        Each product dict should have: title, price, product_url
        Optional: image_url, metadata

        Returns: Number of products processed
        """
        source_id = self.get_source_id(source_name)
        if not source_id:
            raise ValueError(f"Source '{source_name}' not found")

        category_id = None
        if category_slug:
            category_id = self.get_category_id(category_slug)

        count = 0

        with self.db.get_cursor() as cur:
            for product in products:
                try:
                    title = product['title']
                    price_str = product.get('price', '0')
                    price_original = price_str  # Keep original string
                    price = parse_price(price_str)

                    # If price is None (e.g., "Ponuda na upit"), set to 0 but keep original string
                    if price is None:
                        price = Decimal('0')
                        logger.info(f"Product with non-numeric price '{price_str}': {title}")

                    product_url = product.get('link', product.get('product_url', ''))
                    image_url = product.get('image_url')
                    metadata = product.get('metadata')

                    normalized = normalize_title(title)

                    # Upsert using ON CONFLICT
                    cur.execute(
                        """
                        INSERT INTO products (
                            source_id, category_id, title, normalized_title,
                            price, price_original, product_url, image_url, metadata,
                            is_available, last_seen_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true, CURRENT_TIMESTAMP)
                        ON CONFLICT (source_id, product_url) DO UPDATE SET
                            category_id = EXCLUDED.category_id,
                            title = EXCLUDED.title,
                            normalized_title = EXCLUDED.normalized_title,
                            price = EXCLUDED.price,
                            price_original = EXCLUDED.price_original,
                            image_url = EXCLUDED.image_url,
                            metadata = EXCLUDED.metadata,
                            is_available = true,
                            last_seen_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (source_id, category_id, title, normalized, price, price_original,
                         product_url, image_url,
                         psycopg2.extras.Json(metadata) if metadata else None)
                    )
                    count += 1

                except Exception as e:
                    logger.error(f"Failed to insert product {product.get('title')}: {e}")
                    continue

        logger.info(f"Bulk inserted/updated {count} products for {source_name}")
        return count

    def mark_unavailable_products(self, source_name: str, seen_urls: List[str]):
        """
        Mark products as unavailable if they weren't seen in the latest scrape.

        Args:
            source_name: Source to check
            seen_urls: List of product URLs that were seen in this scrape
        """
        source_id = self.get_source_id(source_name)
        if not source_id:
            return

        with self.db.get_cursor() as cur:
            cur.execute(
                """
                UPDATE products
                SET is_available = false,
                    out_of_stock_count = out_of_stock_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE source_id = %s
                  AND product_url NOT IN %s
                  AND is_available = true
                RETURNING id
                """,
                (source_id, tuple(seen_urls) if seen_urls else ('',))
            )
            count = cur.rowcount
            if count > 0:
                logger.info(f"Marked {count} products as unavailable for {source_name}")

    def search_products(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """Full-text search for products."""
        with self.db.get_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM v_current_prices
                WHERE title ILIKE %s
                ORDER BY price ASC
                LIMIT %s OFFSET %s
                """,
                (f'%{query}%', limit, offset)
            )
            return cur.fetchall()

    def get_products_by_category(
        self,
        category_slug: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get products by category, sorted by price."""
        with self.db.get_cursor() as cur:
            cur.execute(
                """
                SELECT * FROM v_current_prices
                WHERE category_slug = %s
                ORDER BY price ASC
                LIMIT %s OFFSET %s
                """,
                (category_slug, limit, offset)
            )
            return cur.fetchall()

    def get_price_history(self, product_id: int, days: int = 30) -> List[Dict]:
        """Get price history for a product."""
        with self.db.get_cursor() as cur:
            cur.execute(
                """
                SELECT price, recorded_at
                FROM price_history
                WHERE product_id = %s
                  AND recorded_at >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY recorded_at ASC
                """,
                (product_id, days)
            )
            return cur.fetchall()


def test_connection():
    """Test database connection."""
    try:
        db = get_db()
        with db.get_cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()
            print(f"✓ Connected to PostgreSQL")
            print(f"  Version: {version['version']}")

            cur.execute("SELECT COUNT(*) as count FROM sources")
            sources = cur.fetchone()
            print(f"  Sources in database: {sources['count']}")

            cur.execute("SELECT COUNT(*) as count FROM products")
            products = cur.fetchone()
            print(f"  Products in database: {products['count']}")

        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test connection
    logging.basicConfig(level=logging.INFO)
    test_connection()
