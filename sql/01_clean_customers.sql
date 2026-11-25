-- =============================================================================
-- 01_clean_customers.sql  ->  view: clean_customers
-- One row per customer. Fixes IDs, blanks, community spelling, household size,
-- mixed dates and duplicate rows, then fills missing household sizes.
-- =============================================================================
CREATE OR REPLACE VIEW clean_customers AS

-- Step 1: standardise every column. Missing markers become NULL (clean_text).
WITH standardised AS (
    SELECT
        clean_id(customer_id)                                   AS customer_id,
        clean_text(full_name)                                   AS full_name,
        clean_text(phone)                                       AS phone,
        LOWER(clean_text(email))                                AS email,

        -- 'rumuola ', 'RUMUOLA' -> 'Rumuola'. First letter upper, the rest lower.
        -- (Community names are one word. PostgreSQL also has INITCAP for this.)
        UPPER(LEFT(clean_text(community), 1))
            || LOWER(SUBSTRING(clean_text(community), 2))       AS community,

        -- '4 people' -> 4. REGEXP_EXTRACT takes the number; TRY_CAST makes it an
        -- integer or NULL. Then a CASE keeps only believable sizes (1 to 30):
        -- '-1' and '45' become NULL.
        CASE
            WHEN TRY_CAST(REGEXP_EXTRACT(LOWER(clean_text(household_size)),
                                         '^(-?[0-9]+)\s*(people|persons)?$', 1) AS INTEGER)
                 BETWEEN 1 AND 30
            THEN TRY_CAST(REGEXP_EXTRACT(LOWER(clean_text(household_size)),
                                         '^(-?[0-9]+)\s*(people|persons)?$', 1) AS INTEGER)
        END                                                     AS household_size_reported,

        clean_id(plan_id)                                       AS plan_id,
        parse_date(signup_date)                                 AS signup_date
    FROM raw_customers
),

-- Step 2: de-duplicate. Some customers were keyed in twice (one copy missing
-- its email). ROW_NUMBER numbers the copies of each customer, most complete first,
-- so keeping row 1 keeps the best copy.
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY
                -- Count the blanks in each copy; fewer blanks wins.
                CAST(email IS NULL AS INTEGER)
                + CAST(phone IS NULL AS INTEGER)
                + CAST(community IS NULL AS INTEGER)
                + CAST(household_size_reported IS NULL AS INTEGER)
                + CAST(plan_id IS NULL AS INTEGER)
                + CAST(signup_date IS NULL AS INTEGER),
                email, phone            -- tie-break so the result never changes run to run
        ) AS copy_number
    FROM standardised
    WHERE customer_id IS NOT NULL
),

deduplicated AS (
    SELECT * EXCLUDE (copy_number)      -- DuckDB-only: EXCLUDE. PostgreSQL lists the columns.
    FROM ranked
    WHERE copy_number = 1
),

-- Step 3: fill missing household sizes with a WINDOW FUNCTION:
-- the average household size of the same community, rounded to a whole person.
-- COALESCE gives the community a business default of 'Unknown' first.
filled AS (
    SELECT
        customer_id,
        full_name,
        phone,
        email,
        COALESCE(community, 'Unknown')                          AS community,
        household_size_reported,
        COALESCE(
            household_size_reported,
            CAST(ROUND(AVG(household_size_reported) OVER (
                PARTITION BY COALESCE(community, 'Unknown')
            )) AS INTEGER)
        )                                                       AS household_size,
        household_size_reported IS NULL                         AS household_size_was_filled,
        plan_id,
        signup_date
    FROM deduplicated
)

SELECT
    *,
    CASE
        WHEN household_size BETWEEN 1 AND 2 THEN '1-2'
        WHEN household_size BETWEEN 3 AND 5 THEN '3-5'
        WHEN household_size >= 6            THEN '6+'
        ELSE 'Unknown'
    END AS household_band
FROM filled;
