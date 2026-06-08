-- Additional indexes for product matching performance
-- Run this after initial schema setup

-- Index on normalized_title for faster ILIKE queries
CREATE INDEX IF NOT EXISTS idx_products_normalized_title_pattern ON products (normalized_title varchar_pattern_ops);

-- Index on price for range queries
CREATE INDEX IF NOT EXISTS idx_products_price_range ON products (price) WHERE is_available = true AND price > 0;

-- Composite index for category + price filtering
CREATE INDEX IF NOT EXISTS idx_products_category_price_available
ON products (category_id, price)
WHERE is_available = true AND price > 0;

-- Index for source + available products
CREATE INDEX IF NOT EXISTS idx_products_source_available
ON products (source_id, is_available)
WHERE is_available = true;

-- Analyze tables to update statistics
ANALYZE products;
ANALYZE product_matches;

-- Show index sizes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'products'
ORDER BY indexname;
