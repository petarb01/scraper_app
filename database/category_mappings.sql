-- ============================================================================
-- CATEGORY MAPPINGS
-- Maps each site's file slugs to canonical categories
-- Canonical categories: WHISKY, VODKA, GIN, RUM, TEQUILA, KONJAK,
--                       RAKIJA, LIKERI, VINO, PIVO, KOKTELI
-- ============================================================================

-- ============================================================================
-- STEP 1: Create source_category_mappings table
-- ============================================================================
-- All 11 canonical categories are defined in schema.sql.
-- Maps each source's raw file slug to a canonical category.
-- file_slug = the filename without _{source_name}.json suffix
-- Example: 'whisky-1' from promili/whisky-1_promili.json maps to canonical 'whisky'

CREATE TABLE IF NOT EXISTS source_category_mappings (
    id                    SERIAL PRIMARY KEY,
    source_id             INTEGER NOT NULL REFERENCES sources(id),
    file_slug             VARCHAR(500) NOT NULL,
    canonical_category_id INTEGER NOT NULL REFERENCES categories(id),
    notes                 TEXT,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_source_slug UNIQUE (source_id, file_slug)
);

CREATE INDEX IF NOT EXISTS idx_src_cat_map_source
    ON source_category_mappings(source_id);

CREATE INDEX IF NOT EXISTS idx_src_cat_map_category
    ON source_category_mappings(canonical_category_id);

-- ============================================================================
-- STEP 2: Insert all mappings
-- All 11 canonical categories across all 5 sources
-- ============================================================================

-- ----------------------------------------------------------------------------
-- WHISKY
-- Sources: all 5 sites
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id) VALUES
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'whisky',
        (SELECT id FROM categories WHERE slug = 'whisky')
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'whiskey',
        (SELECT id FROM categories WHERE slug = 'whisky')
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'whisky',
        (SELECT id FROM categories WHERE slug = 'whisky')
    ),
    (
        (SELECT id FROM sources WHERE name = 'promili'),
        'whisky-1',
        (SELECT id FROM categories WHERE slug = 'whisky')
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'jaka-alkoholna-pica-filter-19-vrsta-jap,Viski,Whiskey,Whisky',
        (SELECT id FROM categories WHERE slug = 'whisky')
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ----------------------------------------------------------------------------
-- VODKA
-- Sources: all 5 sites
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id) VALUES
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'zestoka-cuga-vodka',
        (SELECT id FROM categories WHERE slug = 'vodka')
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'vodka',
        (SELECT id FROM categories WHERE slug = 'vodka')
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'spirits-and-liqueurs-vodka',
        (SELECT id FROM categories WHERE slug = 'vodka')
    ),
    (
        (SELECT id FROM sources WHERE name = 'promili'),
        'vodka-14',
        (SELECT id FROM categories WHERE slug = 'vodka')
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'jaka-alkoholna-pica-filter-19-vrsta-jap,Vodka',
        (SELECT id FROM categories WHERE slug = 'vodka')
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ----------------------------------------------------------------------------
-- GIN
-- Sources: all 5 sites
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id) VALUES
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'zestoka-cuga-gin',
        (SELECT id FROM categories WHERE slug = 'gin')
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'gin',
        (SELECT id FROM categories WHERE slug = 'gin')
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'gin',
        (SELECT id FROM categories WHERE slug = 'gin')
    ),
    (
        (SELECT id FROM sources WHERE name = 'promili'),
        'gin-11',
        (SELECT id FROM categories WHERE slug = 'gin')
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'jaka-alkoholna-pica-filter-19-vrsta-jap,Gin',
        (SELECT id FROM categories WHERE slug = 'gin')
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ----------------------------------------------------------------------------
-- RUM
-- Sources: all 5 sites
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id) VALUES
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'zestoka-cuga-rum',
        (SELECT id FROM categories WHERE slug = 'rum')
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'rum',
        (SELECT id FROM categories WHERE slug = 'rum')
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'rum',
        (SELECT id FROM categories WHERE slug = 'rum')
    ),
    (
        (SELECT id FROM sources WHERE name = 'promili'),
        'rum-13',
        (SELECT id FROM categories WHERE slug = 'rum')
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'jaka-alkoholna-pica-filter-19-vrsta-jap,Rum',
        (SELECT id FROM categories WHERE slug = 'rum')
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ----------------------------------------------------------------------------
-- TEQUILA
-- Sources: all 5 sites
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id) VALUES
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'zestoka-cuga-tequila',
        (SELECT id FROM categories WHERE slug = 'tequila')
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'tequila',
        (SELECT id FROM categories WHERE slug = 'tequila')
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'spirits-and-liqueurs-tequila',
        (SELECT id FROM categories WHERE slug = 'tequila')
    ),
    (
        (SELECT id FROM sources WHERE name = 'promili'),
        'tequila-16',
        (SELECT id FROM categories WHERE slug = 'tequila')
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'jaka-alkoholna-pica-filter-19-vrsta-jap,Tequila',
        (SELECT id FROM categories WHERE slug = 'tequila')
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ----------------------------------------------------------------------------
-- KONJAK (Cognac & Brandy grouped together)
-- Sources: all 5 sites
-- Note: cugaklik splits into cognac + brandy (2 files → same canonical)
--       rotodinamic splits into konjak + brandy (2 files → same canonical)
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id, notes) VALUES
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'zestoka-cuga-cognac',
        (SELECT id FROM categories WHERE slug = 'konjak'),
        'cognac subcategory'
    ),
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'zestoka-cuga-brandy',
        (SELECT id FROM categories WHERE slug = 'konjak'),
        'brandy subcategory'
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'konjak',
        (SELECT id FROM categories WHERE slug = 'konjak'),
        NULL
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'spirits-and-liqueurs-cognac',
        (SELECT id FROM categories WHERE slug = 'konjak'),
        NULL
    ),
    (
        (SELECT id FROM sources WHERE name = 'promili'),
        'cognac-15',
        (SELECT id FROM categories WHERE slug = 'konjak'),
        NULL
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'jaka-alkoholna-pica-filter-19-vrsta-jap,konjak',
        (SELECT id FROM categories WHERE slug = 'konjak'),
        'konjak subcategory'
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'jaka-alkoholna-pica-filter-19-vrsta-jap,Brandy',
        (SELECT id FROM categories WHERE slug = 'konjak'),
        'brandy subcategory'
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ----------------------------------------------------------------------------
-- RAKIJA
-- Sources: all 5 sites
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id) VALUES
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'zestoka-cuga-rakija',
        (SELECT id FROM categories WHERE slug = 'rakija')
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'rakija',
        (SELECT id FROM categories WHERE slug = 'rakija')
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'spirits-and-liqueurs-rakija',
        (SELECT id FROM categories WHERE slug = 'rakija')
    ),
    (
        (SELECT id FROM sources WHERE name = 'promili'),
        'rakija-18',
        (SELECT id FROM categories WHERE slug = 'rakija')
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'jaka-alkoholna-pica-filter-19-vrsta-jap,Rakija',
        (SELECT id FROM categories WHERE slug = 'rakija')
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ----------------------------------------------------------------------------
-- LIKERI (Liqueurs, Bitters, Herbal liqueurs grouped together)
-- Sources: all 5 sites
-- Note: cugaklik splits into 3 files (biljni-liker, bitter, liker)
--       ecuga splits into 2 files (liker, bitter)
--       All map to the same canonical LIKERI category
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id, notes) VALUES
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'zestoka-cuga-biljni-liker',
        (SELECT id FROM categories WHERE slug = 'likeri'),
        'herbal liqueur subcategory'
    ),
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'zestoka-cuga-bitter',
        (SELECT id FROM categories WHERE slug = 'likeri'),
        'bitter subcategory'
    ),
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'zestoka-cuga-liker',
        (SELECT id FROM categories WHERE slug = 'likeri'),
        'liqueur subcategory'
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'liquer',
        (SELECT id FROM categories WHERE slug = 'likeri'),
        NULL
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'spirits-and-liqueurs-liker',
        (SELECT id FROM categories WHERE slug = 'likeri'),
        'liqueur subcategory'
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'spirits-and-liqueurs-bitter',
        (SELECT id FROM categories WHERE slug = 'likeri'),
        'bitter subcategory'
    ),
    (
        (SELECT id FROM sources WHERE name = 'promili'),
        'likeri-12',
        (SELECT id FROM categories WHERE slug = 'likeri'),
        NULL
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'jaka-alkoholna-pica-filter-19-vrsta-jap,Liker',
        (SELECT id FROM categories WHERE slug = 'likeri'),
        NULL
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ----------------------------------------------------------------------------
-- VINO (Wine + Sparkling/Champagne grouped together)
-- Sources: cugaklik, diskontfumar, ecuga, rotodinamic (promili has no wine)
-- Note: diskontfumar's 'sampanjci-i-pjenusci' maps to VINO canonical
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id, notes) VALUES
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'vino',
        (SELECT id FROM categories WHERE slug = 'vino'),
        NULL
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'vino',
        (SELECT id FROM categories WHERE slug = 'vino'),
        NULL
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'sampanjci-i-pjenusci',
        (SELECT id FROM categories WHERE slug = 'vino'),
        'sparkling wine / champagne grouped under vino'
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'vino',
        (SELECT id FROM categories WHERE slug = 'vino'),
        NULL
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'vino',
        (SELECT id FROM categories WHERE slug = 'vino'),
        NULL
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ----------------------------------------------------------------------------
-- PIVO (Beer)
-- Sources: diskontfumar, rotodinamic only (other sites don't carry beer)
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id) VALUES
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'pivo',
        (SELECT id FROM categories WHERE slug = 'pivo')
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'pivo',
        (SELECT id FROM categories WHERE slug = 'pivo')
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ----------------------------------------------------------------------------
-- KOKTELI (Cocktails & Mixers)
-- Sources: cugaklik, diskontfumar, ecuga, rotodinamic (promili has none)
-- ----------------------------------------------------------------------------
INSERT INTO source_category_mappings (source_id, file_slug, canonical_category_id) VALUES
    (
        (SELECT id FROM sources WHERE name = 'cugaklik'),
        'kokteli-i-miksevi',
        (SELECT id FROM categories WHERE slug = 'kokteli')
    ),
    (
        (SELECT id FROM sources WHERE name = 'diskontfumar'),
        'kokteli',
        (SELECT id FROM categories WHERE slug = 'kokteli')
    ),
    (
        (SELECT id FROM sources WHERE name = 'ecuga'),
        'cocktails-mixers',
        (SELECT id FROM categories WHERE slug = 'kokteli')
    ),
    (
        (SELECT id FROM sources WHERE name = 'rotodinamic'),
        'jaka-alkoholna-pica-filter-19-vrsta-jap,Koktel,Koktel miks',
        (SELECT id FROM categories WHERE slug = 'kokteli')
    )
ON CONFLICT ON CONSTRAINT unique_source_slug DO NOTHING;

-- ============================================================================
-- UNMAPPED FILES (require future decisions)
-- ============================================================================
-- The following files exist but have no canonical category yet:
--   - spirits-and-liqueurs-absinth_ecuga.json (ecuga)
--     → Absinth. Suggest: add new canonical category 'absinth' or group under 'likeri'
-- ============================================================================

-- ============================================================================
-- VERIFICATION QUERY
-- Run this after applying the migration to confirm all mappings are correct
-- ============================================================================
-- SELECT
--     s.name as source,
--     scm.file_slug,
--     c.slug as canonical_category,
--     scm.notes
-- FROM source_category_mappings scm
-- JOIN sources s ON scm.source_id = s.id
-- JOIN categories c ON scm.canonical_category_id = c.id
-- ORDER BY c.slug, s.name;
