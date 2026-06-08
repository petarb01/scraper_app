-- ============================================================================
-- VIEW: v_product_groups
-- ============================================================================
-- Purpose:
--   Single source of truth for the browse/search/detail pages.
--   Each row is either:
--     a) A matched group  — group_id = 'g{match_id}',   match_id IS NOT NULL
--     b) A singleton      — group_id = 'p{product_id}', singleton_id IS NOT NULL
--
-- Title priority order (promili first — proper case, no bundle junk):
--   promili → ecuga → diskontfumar → cugaklik → rotodinamic
--
-- store_count counts only stores that currently have the product available
-- at a non-zero price.  LEAST/GREATEST ignore NULLs in PostgreSQL — so
-- min_price/max_price are always the smallest/largest *active* prices.
-- ============================================================================

CREATE OR REPLACE VIEW v_product_groups AS

-- ── Part 1: Matched groups ────────────────────────────────────────────────
-- One row per product_matches row where at least one store actively sells it.
SELECT
    'g' || pm.id::text   AS group_id,
    pm.id                AS match_id,
    NULL::int            AS singleton_id,

    -- Display title: first non-NULL from priority store order
    COALESCE(ppr.title, pe.title, pd.title, pc.title, pr.title)               AS display_title,

    -- Image URL: none currently scraped; structure ready for future
    COALESCE(pe.image_url, pc.image_url, pd.image_url, ppr.image_url, pr.image_url) AS display_image_url,

    -- Volume: all matched products should agree; pick first non-NULL
    COALESCE(pe.volume_ml, pc.volume_ml, pd.volume_ml, ppr.volume_ml, pr.volume_ml) AS volume_ml,

    -- Category: matched products share a category; first non-NULL slug
    COALESCE(ce.slug,  cc.slug,  cd.slug,  cpr.slug,  cr.slug)               AS category_slug,
    COALESCE(ce.display_name, cc.display_name, cd.display_name,
             cpr.display_name, cr.display_name)                               AS category_name,

    -- Price range across all active store prices
    LEAST(pe.price, pc.price, pd.price, ppr.price, pr.price)                  AS min_price,
    GREATEST(pe.price, pc.price, pd.price, ppr.price, pr.price)               AS max_price,

    -- How many stores are actively selling this product right now
    (CASE WHEN pe.id  IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN pc.id  IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN pd.id  IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN ppr.id IS NOT NULL THEN 1 ELSE 0 END +
     CASE WHEN pr.id  IS NOT NULL THEN 1 ELSE 0 END)                          AS store_count

FROM product_matches pm

-- Each LEFT JOIN uses AND conditions so that an unavailable/zero-price
-- product results in all-NULL columns for that store (not counted).
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

-- Skip groups where every store's product is currently unavailable
WHERE COALESCE(pe.id, pc.id, pd.id, ppr.id, pr.id) IS NOT NULL

UNION ALL

-- ── Part 2: Singletons ────────────────────────────────────────────────────
-- Products that have never been matched to a cross-store group.
-- Shown in browse/search so users can still find and buy them.
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
  -- Exclude products already covered by a match group above.
  -- NOT EXISTS with per-column OR lets PostgreSQL use the unique partial
  -- indexes on each source column for efficient lookups.
  AND NOT EXISTS (
      SELECT 1
      FROM   product_matches pm2
      WHERE  pm2.ecuga_id        = p.id
          OR pm2.cugaklik_id     = p.id
          OR pm2.promili_id      = p.id
          OR pm2.diskontfumar_id = p.id
          OR pm2.rotodinamic_id  = p.id
  );
