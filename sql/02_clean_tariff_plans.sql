-- =============================================================================
-- 02_clean_tariff_plans.sql  ->  view: clean_tariff_plans
-- One row per plan. Each plan appears four times with spellings like
-- 'Basic', 'basic ', 'BASIC' and prices like '₦250', '250', '250.00 NGN'.
-- =============================================================================
CREATE OR REPLACE VIEW clean_tariff_plans AS

WITH standardised AS (
    SELECT
        clean_id(plan_id)                                       AS plan_id,
        -- Squeeze repeated inner spaces to one ('g' = replace every match).
        REGEXP_REPLACE(clean_text(plan_name), '\s+', ' ', 'g')  AS plan_name,
        parse_naira(price_per_kwh)                              AS price_per_kwh
    FROM raw_tariff_plans
    WHERE clean_id(plan_id) IS NOT NULL
),

-- The canonical name of each plan is its MOST COMMON spelling.
-- GROUP BY counts each spelling; ROW_NUMBER ranks spellings within each plan.
-- (The most common spelling is already in title case, e.g. 'Productive Use'.)
spellings AS (
    SELECT
        plan_id,
        plan_name,
        COUNT(*) AS times_used,
        ROW_NUMBER() OVER (
            PARTITION BY plan_id
            ORDER BY COUNT(*) DESC, plan_name
        ) AS popularity_rank
    FROM standardised
    WHERE plan_name IS NOT NULL
    GROUP BY plan_id, plan_name
),

-- Every row of a plan carries the same price once parsed, so MAX simply picks it.
-- tests/test_views.py checks that the prices really do agree.
prices AS (
    SELECT plan_id, MAX(price_per_kwh) AS price_per_kwh
    FROM standardised
    GROUP BY plan_id
)

SELECT
    s.plan_id,
    s.plan_name,
    p.price_per_kwh
FROM spellings AS s
INNER JOIN prices AS p ON p.plan_id = s.plan_id
WHERE s.popularity_rank = 1;
