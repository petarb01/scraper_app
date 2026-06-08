-- ============================================================================
-- POSSIBLE MATCHES TABLE — Human review queue
-- ============================================================================
-- Purpose: Holds product groupings that the algorithm is not confident enough
--          to place directly into product_matches.  A human reviewer decides
--          whether each candidate is a real match (confirm) or not (reject).
--
-- Relationship to product_matches:
--   • product_matches  — authoritative, algorithm-confirmed + human-confirmed matches
--   • possible_matches — staging queue; only confirmed rows graduate to product_matches
--
-- The column-per-source shape mirrors product_matches for consistency.
-- group_fingerprint makes the table idempotent across re-scrape cycles: the
-- same candidate is never re-queued once a decision has been recorded.
--
-- Apply to an existing DB:
--   psql -h localhost -p 5433 -U postgres -d price_scraper \
--        -f database/possible_matches.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS possible_matches (
    id               SERIAL PRIMARY KEY,

    -- Candidate product IDs — NULL means that store has no candidate in this group.
    -- ON DELETE SET NULL so a scraped-product removal doesn't cascade-delete a
    -- human decision that may still be relevant for a future product re-import.
    ecuga_id         INTEGER REFERENCES products(id) ON DELETE SET NULL,
    cugaklik_id      INTEGER REFERENCES products(id) ON DELETE SET NULL,
    promili_id       INTEGER REFERENCES products(id) ON DELETE SET NULL,
    diskontfumar_id  INTEGER REFERENCES products(id) ON DELETE SET NULL,
    rotodinamic_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,

    -- Similarity signals from the run that generated this candidate.
    -- Both scores are recorded regardless of which one triggered the suggestion,
    -- giving the reviewer a richer picture.
    jaccard_score    NUMERIC(4, 3) CHECK (jaccard_score BETWEEN 0 AND 1),
    trigram_score    NUMERIC(4, 3) CHECK (trigram_score BETWEEN 0 AND 1),

    -- How this candidate was discovered.
    suggestion_source VARCHAR(50) NOT NULL
        CHECK (suggestion_source IN (
            'near_miss',        -- Jaccard OR trigram in [0.55, 0.70); below main threshold
            'compare_matchers', -- overlap/tfidf algorithm matched but Jaccard did not
            'seed_inspection',  -- seeded from inspection.md ambiguous list (one-time)
            'seed_edge_cases'   -- seeded from edge_cases.md (one-time)
        )),

    -- Stable deduplication key: MD5 of sorted "source_name:product_url" tokens
    -- for every non-null product in the group.  Stable across full DB re-imports
    -- because product URLs come from the stores, not from our ID sequences.
    -- UNIQUE ensures a candidate is never inserted twice regardless of how many
    -- times suggest_matches.py is run.
    group_fingerprint CHAR(32) UNIQUE NOT NULL,

    -- Review lifecycle.
    review_status    VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (review_status IN (
            'pending',   -- awaiting admin decision
            'confirmed', -- admin approved → should be in product_matches
            'rejected'   -- admin rejected → never re-queue this pair
        )),
    reviewed_at      TIMESTAMP,
    reviewer_notes   TEXT,

    -- Once confirmed, points to the product_matches row that was created.
    -- NULL until confirmed; set to NULL again if that product_matches row is
    -- later deleted (ON DELETE SET NULL) so the record of the decision is kept.
    confirmed_match_id  INTEGER REFERENCES product_matches(id) ON DELETE SET NULL,

    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- At least two source columns must be non-null — a single-store candidate
    -- is meaningless as a cross-store match.
    CONSTRAINT at_least_two_sources CHECK (
        (CASE WHEN ecuga_id        IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN cugaklik_id     IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN promili_id      IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN diskontfumar_id IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN rotodinamic_id  IS NOT NULL THEN 1 ELSE 0 END) >= 2
    )
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Admin UI: load pending queue, most-confident first
CREATE INDEX IF NOT EXISTS idx_possible_matches_status_score
    ON possible_matches(review_status, jaccard_score DESC NULLS LAST)
    WHERE review_status = 'pending';

-- History page: all reviewed rows sorted by decision time
CREATE INDEX IF NOT EXISTS idx_possible_matches_reviewed
    ON possible_matches(reviewed_at DESC NULLS LAST)
    WHERE review_status IN ('confirmed', 'rejected');

-- Fast "is this product already queued?" lookup — one partial index per source
CREATE INDEX IF NOT EXISTS idx_pm_ecuga
    ON possible_matches(ecuga_id)        WHERE ecuga_id        IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pm_cugaklik
    ON possible_matches(cugaklik_id)     WHERE cugaklik_id     IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pm_promili
    ON possible_matches(promili_id)      WHERE promili_id       IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pm_diskontfumar
    ON possible_matches(diskontfumar_id) WHERE diskontfumar_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pm_rotodinamic
    ON possible_matches(rotodinamic_id)  WHERE rotodinamic_id  IS NOT NULL;

-- ============================================================================
-- TRIGGER
-- ============================================================================

-- Reuse the update_updated_at_column() function already defined in schema.sql.
CREATE TRIGGER update_possible_matches_updated_at
    BEFORE UPDATE ON possible_matches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE possible_matches IS
    'Human review queue: near-miss and ambiguous product groups awaiting admin decision';

COMMENT ON COLUMN possible_matches.group_fingerprint IS
    'MD5 of sorted "source_name:product_url" pairs — stable across DB re-imports';

COMMENT ON COLUMN possible_matches.suggestion_source IS
    'Pipeline step that generated this candidate (near_miss | compare_matchers | seed_*)';

COMMENT ON COLUMN possible_matches.confirmed_match_id IS
    'FK to product_matches row created when admin confirmed this candidate';
