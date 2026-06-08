-- Migration: add 'superseded' as a valid review_status in possible_matches
-- A row is auto-superseded when another PM candidate that shares one or more
-- of its product IDs is confirmed by a human reviewer.

ALTER TABLE possible_matches
    DROP CONSTRAINT IF EXISTS possible_matches_review_status_check;

ALTER TABLE possible_matches
    ADD CONSTRAINT possible_matches_review_status_check
        CHECK (review_status IN ('pending', 'confirmed', 'rejected', 'superseded'));

COMMENT ON COLUMN possible_matches.review_status IS
    'pending = awaiting review; confirmed = human verified; '
    'rejected = human rejected; '
    'superseded = auto-dismissed because every product in this group '
    'was already matched via another confirmed candidate';
