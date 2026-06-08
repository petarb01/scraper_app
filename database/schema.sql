-- ============================================================================
-- Web Scraper Database Schema - PostgreSQL
-- ============================================================================
-- Purpose: Store and compare product prices from multiple e-commerce sources
-- Optimized for: Fast searches, price comparisons, price history tracking
-- ============================================================================

-- Drop tables if they exist (for clean reinstall)
DROP TABLE IF EXISTS price_history CASCADE;
DROP TABLE IF EXISTS product_matches CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS sources CASCADE;

-- ============================================================================
-- SOURCES TABLE
-- ============================================================================
-- Stores information about different e-commerce websites being scraped

CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,           -- Internal name: 'ecuga', 'cugaklik'
    display_name VARCHAR(200) NOT NULL,          -- Display name: 'E-Cuga', 'Cugaklik'
    website_url VARCHAR(500),                    -- Homepage URL
    logo_url VARCHAR(500),                       -- Logo image URL
    is_active BOOLEAN DEFAULT true,              -- Enable/disable scraping
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial sources
INSERT INTO sources (name, display_name, website_url, is_active) VALUES
    ('ecuga', 'E-Cuga', 'https://ecuga.com', true),
    ('cugaklik', 'Cugaklik', 'https://www.cugaklik.hr', true),
    ('promili', 'Promili', 'https://promili.hr', true),
    ('diskontfumar', 'Diskont Fumar', 'https://diskontfumar.hr', true),
    ('rotodinamic', 'Rotodinamic', 'https://rotodinamic.hr', true);

-- ============================================================================
-- CATEGORIES TABLE
-- ============================================================================
-- Product categories (whisky, vino, gin, etc.)
-- Supports hierarchical categories with parent_id

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,                  -- Internal name
    display_name VARCHAR(200) NOT NULL,          -- Display name for users
    slug VARCHAR(100) UNIQUE NOT NULL,           -- URL-friendly: 'whisky', 'vino'
    parent_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,  -- For subcategories
    description TEXT,                            -- Category description
    icon VARCHAR(100),                           -- Icon name/class
    sort_order INTEGER DEFAULT 0,               -- Display order
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert canonical categories (11 total)
-- These are the only categories used in the system.
-- Site-specific category names are mapped to these via source_category_mappings table.
INSERT INTO categories (name, display_name, slug, sort_order) VALUES
    ('whisky',  'Whisky',            'whisky',  1),
    ('vodka',   'Vodka',             'vodka',   2),
    ('gin',     'Gin',               'gin',     3),
    ('rum',     'Rum',               'rum',     4),
    ('tequila', 'Tequila',           'tequila', 5),
    ('konjak',  'Konjak & Brandy',   'konjak',  6),
    ('rakija',  'Rakija',            'rakija',  7),
    ('likeri',  'Likeri',            'likeri',  8),
    ('vino',    'Vino',              'vino',    9),
    ('pivo',    'Pivo',              'pivo',    10),
    ('kokteli', 'Kokteli i Miksevi', 'kokteli', 11);

-- ============================================================================
-- PRODUCTS TABLE (CORE TABLE)
-- ============================================================================
-- Stores all products from all sources

CREATE TABLE products (
    id SERIAL PRIMARY KEY,

    -- Foreign keys
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,

    -- Product information
    title VARCHAR(500) NOT NULL,                 -- Original product title
    normalized_title VARCHAR(500),               -- Cleaned/normalized for matching
    slug VARCHAR(500),                           -- URL-friendly version
    volume_ml SMALLINT,                          -- Volume in ml (e.g. 700 for 0.7l) — used for matching

    -- Pricing
    price NUMERIC(10, 2) NOT NULL,              -- Current price (numeric for sorting)
    price_original VARCHAR(50),                  -- Original scraped text: "99,99€"
    currency VARCHAR(10) DEFAULT 'EUR',

    -- Links
    product_url TEXT NOT NULL,                   -- Full product URL
    image_url TEXT,                              -- Product image URL

    -- Product details (flexible JSON storage)
    metadata JSONB,                              -- volume, ABV, brand, description, etc.

    -- Availability tracking
    is_available BOOLEAN DEFAULT true,           -- Currently in stock
    out_of_stock_count INTEGER DEFAULT 0,       -- Times seen as out of stock

    -- Timestamps
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- First time scraped
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,   -- Last time scraped
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure unique products per source
    CONSTRAINT unique_product_per_source UNIQUE(source_id, product_url)
);

-- ============================================================================
-- INDEXES FOR PRODUCTS TABLE (Performance optimization)
-- ============================================================================

-- Foreign key indexes
CREATE INDEX idx_products_source ON products(source_id);
CREATE INDEX idx_products_category ON products(category_id);

-- Search and filter indexes
CREATE INDEX idx_products_price ON products(price);
CREATE INDEX idx_products_available ON products(is_available);
CREATE INDEX idx_products_normalized ON products(normalized_title);
CREATE INDEX idx_products_updated ON products(updated_at);

-- Full-text search index (for product name searches)
CREATE INDEX idx_products_title_fts ON products USING gin(to_tsvector('simple', title));

-- Composite indexes for common queries
CREATE INDEX idx_products_category_price ON products(category_id, price) WHERE is_available = true;
CREATE INDEX idx_products_source_available ON products(source_id, is_available);

-- JSONB index for metadata searches
CREATE INDEX idx_products_metadata ON products USING gin(metadata);

-- ============================================================================
-- PRICE HISTORY TABLE
-- ============================================================================
-- Track price changes over time for each product

CREATE TABLE price_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    price NUMERIC(10, 2) NOT NULL,
    was_available BOOLEAN DEFAULT true,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for price history
CREATE INDEX idx_price_history_product ON price_history(product_id);
CREATE INDEX idx_price_history_date ON price_history(recorded_at);
CREATE INDEX idx_price_history_product_date ON price_history(product_id, recorded_at DESC);

-- ============================================================================
-- PRODUCT MATCHES TABLE
-- ============================================================================
-- Links same products across different sources (for price comparison)

-- Each row = one matched product group (same product across stores).
-- NULL in a source column means that store doesn't carry this product.
CREATE TABLE product_matches (
    id               SERIAL PRIMARY KEY,
    ecuga_id         INTEGER REFERENCES products(id) ON DELETE SET NULL,
    cugaklik_id      INTEGER REFERENCES products(id) ON DELETE SET NULL,
    promili_id       INTEGER REFERENCES products(id) ON DELETE SET NULL,
    diskontfumar_id  INTEGER REFERENCES products(id) ON DELETE SET NULL,
    rotodinamic_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Partial indexes — fast lookup: "is this product already matched?"
CREATE INDEX idx_matches_ecuga        ON product_matches(ecuga_id)        WHERE ecuga_id IS NOT NULL;
CREATE INDEX idx_matches_cugaklik     ON product_matches(cugaklik_id)     WHERE cugaklik_id IS NOT NULL;
CREATE INDEX idx_matches_promili      ON product_matches(promili_id)      WHERE promili_id IS NOT NULL;
CREATE INDEX idx_matches_diskontfumar ON product_matches(diskontfumar_id) WHERE diskontfumar_id IS NOT NULL;
CREATE INDEX idx_matches_rotodinamic  ON product_matches(rotodinamic_id)  WHERE rotodinamic_id IS NOT NULL;

-- Unique partial indexes — each product can appear in at most one match group.
-- insert_match_row() uses ON CONFLICT DO NOTHING to silently skip algorithm
-- rows that would duplicate a human-confirmed row.
CREATE UNIQUE INDEX uq_pm_ecuga_id        ON product_matches(ecuga_id)        WHERE ecuga_id IS NOT NULL;
CREATE UNIQUE INDEX uq_pm_cugaklik_id     ON product_matches(cugaklik_id)     WHERE cugaklik_id IS NOT NULL;
CREATE UNIQUE INDEX uq_pm_promili_id      ON product_matches(promili_id)      WHERE promili_id IS NOT NULL;
CREATE UNIQUE INDEX uq_pm_diskontfumar_id ON product_matches(diskontfumar_id) WHERE diskontfumar_id IS NOT NULL;
CREATE UNIQUE INDEX uq_pm_rotodinamic_id  ON product_matches(rotodinamic_id)  WHERE rotodinamic_id IS NOT NULL;

-- ============================================================================
-- VIEWS (Convenient queries)
-- ============================================================================

-- View: Latest prices with source information
CREATE VIEW v_current_prices AS
SELECT
    p.id,
    p.title,
    p.price,
    p.currency,
    p.product_url,
    p.image_url,
    p.is_available,
    c.display_name as category,
    c.slug as category_slug,
    s.display_name as source,
    s.name as source_name,
    s.website_url as source_url,
    p.last_seen_at,
    p.metadata
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
JOIN sources s ON p.source_id = s.id
WHERE p.is_available = true;

-- View: Product price comparison (matched products across all stores)
-- One row per matched group. NULL columns = that store doesn't carry the product.
CREATE VIEW v_price_comparison AS
SELECT
    pm.id                   AS match_id,
    COALESCE(p1.title, p2.title, p3.title, p4.title, p5.title) AS title,
    COALESCE(p1.volume_ml, p2.volume_ml, p3.volume_ml, p4.volume_ml, p5.volume_ml) AS volume_ml,

    p1.id                   AS ecuga_product_id,
    p1.price                AS ecuga_price,
    p1.product_url          AS ecuga_url,

    p2.id                   AS cugaklik_product_id,
    p2.price                AS cugaklik_price,
    p2.product_url          AS cugaklik_url,

    p3.id                   AS promili_product_id,
    p3.price                AS promili_price,
    p3.product_url          AS promili_url,

    p4.id                   AS diskontfumar_product_id,
    p4.price                AS diskontfumar_price,
    p4.product_url          AS diskontfumar_url,

    p5.id                   AS rotodinamic_product_id,
    p5.price                AS rotodinamic_price,
    p5.product_url          AS rotodinamic_url,

    LEAST(p1.price, p2.price, p3.price, p4.price, p5.price) AS min_price,
    GREATEST(p1.price, p2.price, p3.price, p4.price, p5.price) AS max_price

FROM product_matches pm
LEFT JOIN products p1 ON pm.ecuga_id        = p1.id
LEFT JOIN products p2 ON pm.cugaklik_id     = p2.id
LEFT JOIN products p3 ON pm.promili_id      = p3.id
LEFT JOIN products p4 ON pm.diskontfumar_id = p4.id
LEFT JOIN products p5 ON pm.rotodinamic_id  = p5.id;

-- ============================================================================
-- VIEW: v_product_groups
-- ============================================================================
-- Single source of truth for browse/search/detail pages.
-- Rows:
--   a) Matched groups  — group_id = 'g{match_id}',   match_id IS NOT NULL
--   b) Singletons      — group_id = 'p{product_id}', singleton_id IS NOT NULL
--
-- Title priority (promili first — proper case, no bundle junk):
--   promili → ecuga → diskontfumar → cugaklik → rotodinamic
--
-- Each LEFT JOIN uses AND conditions so an unavailable/zero-price store
-- contributes NULL columns (not counted in store_count).
-- LEAST/GREATEST ignore NULLs, giving correct min/max from active stores only.

CREATE OR REPLACE VIEW v_product_groups AS

-- Part 1: Matched groups
SELECT
    'g' || pm.id::text   AS group_id,
    pm.id                AS match_id,
    NULL::int            AS singleton_id,
    COALESCE(ppr.title, pe.title, pd.title, pc.title, pr.title)               AS display_title,
    COALESCE(pe.image_url, pc.image_url, pd.image_url, ppr.image_url, pr.image_url) AS display_image_url,
    COALESCE(pe.volume_ml, pc.volume_ml, pd.volume_ml, ppr.volume_ml, pr.volume_ml) AS volume_ml,
    COALESCE(ce.slug,  cc.slug,  cd.slug,  cpr.slug,  cr.slug)               AS category_slug,
    COALESCE(ce.display_name, cc.display_name, cd.display_name,
             cpr.display_name, cr.display_name)                               AS category_name,
    LEAST(pe.price, pc.price, pd.price, ppr.price, pr.price)                  AS min_price,
    GREATEST(pe.price, pc.price, pd.price, ppr.price, pr.price)               AS max_price,
    (CASE WHEN pe.id  IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN pc.id  IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN pd.id  IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN ppr.id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN pr.id  IS NOT NULL THEN 1 ELSE 0 END)                          AS store_count
FROM product_matches pm
LEFT JOIN products    pe  ON pe.id   = pm.ecuga_id        AND pe.is_available  AND pe.price  > 0
LEFT JOIN categories  ce  ON ce.id   = pe.category_id
LEFT JOIN products    pc  ON pc.id   = pm.cugaklik_id     AND pc.is_available  AND pc.price  > 0
LEFT JOIN categories  cc  ON cc.id   = pc.category_id
LEFT JOIN products    pd  ON pd.id   = pm.diskontfumar_id AND pd.is_available  AND pd.price  > 0
LEFT JOIN categories  cd  ON cd.id   = pd.category_id
LEFT JOIN products    ppr ON ppr.id  = pm.promili_id      AND ppr.is_available AND ppr.price > 0
LEFT JOIN categories  cpr ON cpr.id  = ppr.category_id
LEFT JOIN products    pr  ON pr.id   = pm.rotodinamic_id  AND pr.is_available  AND pr.price  > 0
LEFT JOIN categories  cr  ON cr.id   = pr.category_id
WHERE COALESCE(pe.id, pc.id, pd.id, ppr.id, pr.id) IS NOT NULL

UNION ALL

-- Part 2: Singletons (products in no match group)
SELECT
    'p' || p.id::text    AS group_id,
    NULL::int            AS match_id,
    p.id                 AS singleton_id,
    p.title              AS display_title,
    p.image_url          AS display_image_url,
    p.volume_ml,
    c.slug               AS category_slug,
    c.display_name       AS category_name,
    p.price              AS min_price,
    p.price              AS max_price,
    1                    AS store_count
FROM products p
LEFT JOIN categories c ON c.id = p.category_id
WHERE p.is_available
  AND p.price > 0
  AND NOT EXISTS (
      SELECT 1
      FROM   product_matches pm2
      WHERE  pm2.ecuga_id        = p.id
          OR pm2.cugaklik_id     = p.id
          OR pm2.promili_id      = p.id
          OR pm2.diskontfumar_id = p.id
          OR pm2.rotodinamic_id  = p.id
  );

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on products
CREATE TRIGGER update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger to auto-update updated_at on sources
CREATE TRIGGER update_sources_updated_at
    BEFORE UPDATE ON sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to normalize product titles for matching
CREATE OR REPLACE FUNCTION normalize_title(title TEXT)
RETURNS TEXT AS $$
BEGIN
    -- Convert to lowercase, remove extra spaces, remove special chars
    RETURN LOWER(REGEXP_REPLACE(TRIM(title), '[^a-z0-9\s]', '', 'gi'));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to record price history when price changes
CREATE OR REPLACE FUNCTION record_price_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only record if price actually changed
    IF NEW.price <> OLD.price OR NEW.is_available <> OLD.is_available THEN
        INSERT INTO price_history (product_id, price, was_available)
        VALUES (NEW.id, NEW.price, NEW.is_available);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically record price changes
CREATE TRIGGER track_price_changes
    AFTER UPDATE OF price, is_available ON products
    FOR EACH ROW
    EXECUTE FUNCTION record_price_change();

-- ============================================================================
-- COMMENTS (Documentation)
-- ============================================================================

COMMENT ON TABLE sources IS 'E-commerce websites being scraped';
COMMENT ON TABLE categories IS 'Product categories (whisky, vino, gin, etc.)';
COMMENT ON TABLE products IS 'All products from all sources';
COMMENT ON TABLE price_history IS 'Historical price data for tracking changes';
COMMENT ON TABLE product_matches IS 'One row per matched product group — one column per store (NULL if store lacks the product)';

COMMENT ON COLUMN products.normalized_title IS 'Cleaned title for fuzzy matching';
COMMENT ON COLUMN products.metadata IS 'Additional product info (volume, ABV, etc.) stored as JSON';

-- ============================================================================
-- GRANTS (Security - adjust for your setup)
-- ============================================================================

-- Create application user (uncomment and adjust as needed)
-- CREATE USER scraper_app WITH PASSWORD 'your_secure_password';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO scraper_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO scraper_app;

-- ============================================================================
-- SAMPLE QUERIES (for testing)
-- ============================================================================

-- Count products per source
-- SELECT s.display_name, COUNT(p.id) as product_count
-- FROM sources s
-- LEFT JOIN products p ON s.id = p.source_id
-- GROUP BY s.display_name;

-- Find cheapest whisky
-- SELECT title, price, source_id FROM products
-- WHERE category_id = (SELECT id FROM categories WHERE slug = 'whisky')
-- ORDER BY price ASC LIMIT 10;

-- Search for product
-- SELECT * FROM v_current_prices
-- WHERE title ILIKE '%jack daniel%'
-- ORDER BY price ASC;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
