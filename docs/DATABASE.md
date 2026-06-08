# Database Documentation

Complete reference for the PostgreSQL database schema, queries, and product matching.

## Database Overview

**Database:** `price_scraper`
**Version:** PostgreSQL 15
**Total Products:** 4,972+
**Vendors:** 5
**Categories:** 14
**Product Matches:** ~420

## Schema

### Tables

#### 1. `sources`
Stores vendor/website information.

```sql
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Data:**
- E-Cuga (ecuga.com)
- Cugaklik (cugaklik.hr)
- Promili (promili.hr)
- Diskont Fumar (diskontfumar.hr)
- Rotodinamic (rotodinamic.hr)

#### 2. `categories`
Product categories.

```sql
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Data:**
- whisky, gin, rum, vodka, tequila, cognac, rakija, likeri (liqueurs)
- vino (wine), pivo (beer), sampanjci (champagne), kokteli (cocktails)
- jaka-alkoholna-pica (spirits), zestoka-cuga (hard liquor)

#### 3. `products`
All products from all vendors.

```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id),
    category_id INTEGER REFERENCES categories(id),
    title TEXT NOT NULL,
    price DECIMAL(10, 2),
    url TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
```sql
CREATE INDEX idx_products_source ON products(source_id);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_price ON products(price);
CREATE INDEX idx_products_title_gin ON products USING gin(to_tsvector('english', title));
```

#### 4. `price_history`
Historical price tracking (auto-populated by trigger).

```sql
CREATE TABLE price_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL(10, 2) NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Trigger:**
```sql
CREATE TRIGGER track_price_changes
    AFTER UPDATE OF price ON products
    FOR EACH ROW
    WHEN (OLD.price IS DISTINCT FROM NEW.price)
    EXECUTE FUNCTION log_price_change();
```

#### 5. `product_matches`
Links same products across different vendors.

```sql
CREATE TABLE product_matches (
    id SERIAL PRIMARY KEY,
    product1_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    product2_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    confidence DECIMAL(3, 2),
    matched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product1_id, product2_id)
);
```

**Indexes:**
```sql
CREATE INDEX idx_matches_product1 ON product_matches(product1_id);
CREATE INDEX idx_matches_product2 ON product_matches(product2_id);
CREATE INDEX idx_matches_confidence ON product_matches(confidence);
```

## Views

### `v_current_prices`
Convenient view with denormalized data.

```sql
CREATE VIEW v_current_prices AS
SELECT
    p.id,
    p.title,
    p.price,
    p.url,
    s.name as source_name,
    c.name as category_name,
    c.slug as category_slug,
    p.updated_at
FROM products p
JOIN sources s ON p.source_id = s.id
JOIN categories c ON p.category_id = c.id;
```

## Common Queries

### Search Products

**Full-text search:**
```sql
SELECT * FROM v_current_prices
WHERE to_tsvector('english', title) @@ to_tsquery('english', 'jack & daniel')
ORDER BY price ASC;
```

**Simple search (case-insensitive):**
```sql
SELECT * FROM v_current_prices
WHERE title ILIKE '%jack daniel%'
ORDER BY price ASC
LIMIT 50;
```

### Filter by Category

```sql
SELECT * FROM v_current_prices
WHERE category_slug = 'whisky'
ORDER BY price ASC;
```

### Filter by Vendor

```sql
SELECT * FROM v_current_prices
WHERE source_name = 'E-Cuga'
ORDER BY price ASC;
```

### Price Range

```sql
SELECT * FROM v_current_prices
WHERE price BETWEEN 50.00 AND 100.00
ORDER BY price ASC;
```

### Price Comparison (Matched Products)

```sql
SELECT
    p1.title as product1_title,
    s1.name as vendor1,
    p1.price as price1,
    p2.title as product2_title,
    s2.name as vendor2,
    p2.price as price2,
    (p1.price - p2.price) as price_difference,
    pm.confidence
FROM product_matches pm
JOIN products p1 ON pm.product1_id = p1.id
JOIN products p2 ON pm.product2_id = p2.id
JOIN sources s1 ON p1.source_id = s1.id
JOIN sources s2 ON p2.source_id = s2.id
WHERE pm.confidence > 0.85
ORDER BY ABS(p1.price - p2.price) DESC;
```

### Price History

**Get price history for a product:**
```sql
SELECT price, recorded_at
FROM price_history
WHERE product_id = 123
ORDER BY recorded_at DESC;
```

**Products with recent price changes:**
```sql
SELECT DISTINCT p.id, p.title, p.price
FROM products p
JOIN price_history ph ON p.id = ph.product_id
WHERE ph.recorded_at >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY ph.recorded_at DESC;
```

**Price drops in last week:**
```sql
SELECT
    p.title,
    p.price as current_price,
    ph.price as old_price,
    (ph.price - p.price) as savings,
    ROUND((ph.price - p.price) / ph.price * 100, 2) as discount_percent
FROM products p
JOIN price_history ph ON p.id = ph.product_id
WHERE ph.recorded_at >= CURRENT_DATE - INTERVAL '7 days'
  AND p.price < ph.price
ORDER BY savings DESC
LIMIT 20;
```

### Statistics

**Products per vendor:**
```sql
SELECT s.name, COUNT(*) as product_count
FROM products p
JOIN sources s ON p.source_id = s.id
GROUP BY s.name
ORDER BY product_count DESC;
```

**Average price per category:**
```sql
SELECT c.name, AVG(p.price) as avg_price, COUNT(*) as products
FROM products p
JOIN categories c ON p.category_id = c.id
WHERE p.price IS NOT NULL
GROUP BY c.name
ORDER BY avg_price DESC;
```

**Cheapest vendor by category:**
```sql
SELECT
    c.name as category,
    s.name as vendor,
    AVG(p.price) as avg_price
FROM products p
JOIN sources s ON p.source_id = s.id
JOIN categories c ON p.category_id = c.id
WHERE p.price IS NOT NULL
GROUP BY c.name, s.name
ORDER BY c.name, avg_price ASC;
```

## Product Matching

### How It Works

The product matching algorithm identifies the same product across different vendors using fuzzy string matching.

**Matching Process:**
1. Extract brand from title
2. Normalize title (remove special chars, lowercase)
3. Extract volume/size (e.g., "700ml", "0.7L")
4. Calculate string similarity (Levenshtein distance)
5. Validate price range (prices should be similar)
6. Assign confidence score (0.0 - 1.0)

**Confidence Threshold:** 0.75 (75% similarity)

### Running the Matcher

```bash
# Match all products
python3 database/product_matcher.py --match-all --confidence 0.75

# Match specific category
python3 database/product_matcher.py --category whisky --confidence 0.80

# Dry run (no database writes)
python3 database/product_matcher.py --match-all --dry-run
```

### Matching Factors

| Factor | Weight | Description |
|--------|--------|-------------|
| Title similarity | 40% | Levenshtein distance on normalized titles |
| Brand match | 30% | Extracted brand names must match |
| Volume match | 15% | Product size/volume should match |
| Price range | 10% | Prices should be within reasonable range |
| Category | 5% | Same category bonus |

### Example Matches

**High Confidence (>0.90):**
- "Jack Daniel's Tennessee Whiskey 0.7L" (E-Cuga)
- "Jack Daniels Tennessee Whiskey 700ml" (Cugaklik)

**Medium Confidence (0.75-0.90):**
- "Johnnie Walker Black Label" (Promili)
- "Johnnie Walker Black Label Whisky" (Diskont Fumar)

**Low Confidence (<0.75):**
- Rejected, not matched

## Data Migration

### Importing JSON Data

```bash
# Test connection
python3 database/db_utils.py

# Import all JSON files
python3 database/migrate_json_to_db.py --verify

# Import specific vendor
python3 database/migrate_json_to_db.py --source ecuga
```

### Exporting Data

**Export to JSON:**
```bash
psql -h localhost -U postgres -d price_scraper -c \
  "COPY (SELECT row_to_json(t) FROM v_current_prices t) TO STDOUT" \
  > products_export.json
```

**Export to CSV:**
```bash
psql -h localhost -U postgres -d price_scraper -c \
  "COPY v_current_prices TO STDOUT CSV HEADER" \
  > products_export.csv
```

## Backup & Restore

### Backup

```bash
# Full database backup
docker exec price_scraper_db pg_dump -U postgres price_scraper > backup.sql

# Compressed backup
docker exec price_scraper_db pg_dump -U postgres price_scraper | gzip > backup.sql.gz

# Only schema
docker exec price_scraper_db pg_dump -U postgres --schema-only price_scraper > schema_backup.sql

# Only data
docker exec price_scraper_db pg_dump -U postgres --data-only price_scraper > data_backup.sql
```

### Restore

```bash
# Restore from backup
cat backup.sql | docker exec -i price_scraper_db psql -U postgres -d price_scraper

# Restore compressed backup
gunzip -c backup.sql.gz | docker exec -i price_scraper_db psql -U postgres -d price_scraper
```

## Performance Optimization

### Vacuum & Analyze

```bash
# Analyze tables (update statistics)
docker exec price_scraper_db psql -U postgres -d price_scraper -c "ANALYZE;"

# Vacuum (reclaim space)
docker exec price_scraper_db psql -U postgres -d price_scraper -c "VACUUM;"

# Full vacuum analyze
docker exec price_scraper_db psql -U postgres -d price_scraper -c "VACUUM ANALYZE;"
```

### Index Maintenance

```bash
# Reindex all tables
docker exec price_scraper_db psql -U postgres -d price_scraper -c "REINDEX DATABASE price_scraper;"

# Reindex specific table
docker exec price_scraper_db psql -U postgres -d price_scraper -c "REINDEX TABLE products;"
```

### Query Performance

**Check slow queries:**
```sql
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

**Explain query plan:**
```sql
EXPLAIN ANALYZE
SELECT * FROM v_current_prices
WHERE title ILIKE '%whisky%'
ORDER BY price ASC;
```

## Maintenance Tasks

### Daily
- Automatic via scrapers and triggers
- Price history auto-logged
- Database remains up-to-date

### Weekly
```bash
# Run product matcher for new products
python3 database/product_matcher.py --match-all --confidence 0.75

# Analyze database
docker exec price_scraper_db psql -U postgres -d price_scraper -c "ANALYZE;"
```

### Monthly
```bash
# Backup database
docker exec price_scraper_db pg_dump -U postgres price_scraper | gzip > backup_$(date +%Y%m%d).sql.gz

# Vacuum database
docker exec price_scraper_db psql -U postgres -d price_scraper -c "VACUUM ANALYZE;"

# Check database size
docker exec price_scraper_db psql -U postgres -d price_scraper -c \
  "SELECT pg_size_pretty(pg_database_size('price_scraper'));"
```

## Troubleshooting

### Connection Issues

```bash
# Test connection
psql -h localhost -U postgres -d price_scraper

# Check if database is running
docker ps | grep price_scraper_db

# View database logs
docker logs price_scraper_db
```

### Performance Issues

```bash
# Check table sizes
docker exec price_scraper_db psql -U postgres -d price_scraper -c \
  "SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Check index usage
docker exec price_scraper_db psql -U postgres -d price_scraper -c \
  "SELECT schemaname, tablename, indexname, idx_scan
   FROM pg_stat_user_indexes ORDER BY idx_scan ASC;"
```

### Data Integrity

```bash
# Check for orphaned records
docker exec price_scraper_db psql -U postgres -d price_scraper -c \
  "SELECT COUNT(*) FROM products WHERE source_id NOT IN (SELECT id FROM sources);"

# Verify foreign keys
docker exec price_scraper_db psql -U postgres -d price_scraper -c \
  "SELECT conname, conrelid::regclass, confrelid::regclass
   FROM pg_constraint WHERE contype = 'f';"
```

## API Integration

### Python Example (using db_utils.py)

```python
from database.db_utils import DatabaseConfig, ProductRepository

# Initialize repository
config = DatabaseConfig()
repo = ProductRepository(config)

# Search products
products = repo.search_products("whisky", limit=50)

# Get by category
products = repo.get_by_category("whisky")

# Get product matches
matches = repo.get_product_matches(confidence_threshold=0.80)
```

### Direct SQL from Backend

```python
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host="db",
    port=5432,
    database="price_scraper",
    user="postgres",
    password="strongpassword"
)

with conn.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("SELECT * FROM v_current_prices WHERE title ILIKE %s", ('%whisky%',))
    products = cur.fetchall()
```

---

**For more information, see [README.md](../README.md)**
