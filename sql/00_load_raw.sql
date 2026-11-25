-- =============================================================================
-- 00_load_raw.sql
-- Load the four messy CSV files into raw_* tables, every column as text (VARCHAR),
-- and define the small helper macros the cleaning views share.
--
-- {raw_dir} is replaced by run.py with the folder that holds the CSV files.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Helper macros
-- DuckDB-only syntax: CREATE MACRO. In PostgreSQL the same idea is
-- CREATE FUNCTION clean_text(x TEXT) RETURNS TEXT AS $$ ... $$ LANGUAGE SQL;
-- -----------------------------------------------------------------------------

-- The ONE definition of "missing", used by every view.
-- 1. TRIM removes spaces around the value.
-- 2. A missing-token check turns 'N/A', 'none', '-', 'null' (any case) into NULL.
-- 3. NULLIF(TRIM(x), '') turns an empty string into NULL.
CREATE OR REPLACE MACRO clean_text(x) AS
    CASE
        WHEN LOWER(TRIM(x)) IN ('n/a', 'na', 'none', '-', 'null', 'nan') THEN NULL
        ELSE NULLIF(TRIM(x), '')
    END;

-- Customer, plan and payment IDs: " mg-0042 " -> 'MG-0042'.
CREATE OR REPLACE MACRO clean_id(x) AS
    UPPER(REPLACE(clean_text(x), ' ', ''));

-- Mixed date formats, tried in order. COALESCE returns the first one that worked.
-- TRY_STRPTIME returns NULL instead of failing when the text does not match.
-- Slash dates are DAY-FIRST (Nigerian convention): 05/03/2026 is 5 March 2026.
-- DuckDB-only: TRY_STRPTIME. PostgreSQL would use TO_DATE inside a guarded CASE.
CREATE OR REPLACE MACRO parse_date(x) AS
    CAST(
        COALESCE(
            TRY_STRPTIME(clean_text(x), '%Y-%m-%d'),   -- 2026-03-05
            TRY_STRPTIME(clean_text(x), '%Y/%m/%d'),   -- 2026/03/05
            TRY_STRPTIME(clean_text(x), '%d/%m/%Y'),   -- 05/03/2026 (day first)
            TRY_STRPTIME(clean_text(x), '%d %b %Y')    -- 5 Mar 2026
        ) AS DATE
    );

-- Naira amounts in any format: '₦5,000', 'N5,000', 'NGN 5000', '5000.00', '250.00 NGN'.
-- REGEXP_EXTRACT pulls out the digits (group 1), REPLACE drops the thousands commas,
-- TRY_CAST turns the text into a number (or NULL if it is not one).
CREATE OR REPLACE MACRO parse_naira(x) AS
    TRY_CAST(
        REPLACE(
            REGEXP_EXTRACT(
                LOWER(clean_text(x)),
                '^(?:₦|ngn|n)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:ngn)?$',
                1
            ),
            ',', ''
        ) AS DOUBLE
    );


-- -----------------------------------------------------------------------------
-- Raw tables: an exact copy of each file, all text. No cleaning happens here.
-- DuckDB-only: read_csv(). In PostgreSQL: CREATE TABLE ... then COPY ... FROM.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE raw_customers AS
SELECT * FROM read_csv('{raw_dir}/customers.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE raw_tariff_plans AS
SELECT * FROM read_csv('{raw_dir}/tariff_plans.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE raw_meter_readings AS
SELECT * FROM read_csv('{raw_dir}/meter_readings.csv', header = true, all_varchar = true);

CREATE OR REPLACE TABLE raw_payments AS
SELECT * FROM read_csv('{raw_dir}/payments.csv', header = true, all_varchar = true);
