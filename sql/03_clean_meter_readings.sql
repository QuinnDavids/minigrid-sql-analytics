-- =============================================================================
-- 03_clean_meter_readings.sql  ->  view: clean_meter_readings
-- One row per customer per day. Pulls numbers out of text, converts units,
-- blanks impossible values and removes duplicate readings.
-- =============================================================================
CREATE OR REPLACE VIEW clean_meter_readings AS

-- Step 1: standardise text. Lower case makes unit matching simple ('kWh' -> 'kwh').
WITH standardised AS (
    SELECT
        clean_id(customer_id)               AS customer_id,
        parse_date(reading_date)            AS reading_date,
        LOWER(clean_text(energy_used))      AS energy_text,
        LOWER(clean_text(peak_load_kw))     AS peak_text,
        LOWER(clean_text(outage_hours))     AS outage_text
    FROM raw_meter_readings
),

-- Step 2: split each value into a number and a unit with REGEXP_EXTRACT.
-- Pattern: optional minus, digits, optional decimals, optional spaces, optional unit.
-- Group 1 is the number, group 3 the unit. 'error' does not match, so its number is
-- '' and TRY_CAST turns that into NULL.
parsed AS (
    SELECT
        customer_id,
        reading_date,
        TRY_CAST(REGEXP_EXTRACT(energy_text, '^(-?[0-9]+(\.[0-9]+)?)\s*(kwh|wh)?$', 1) AS DOUBLE)
                                                                        AS energy_number,
        REGEXP_EXTRACT(energy_text, '^(-?[0-9]+(\.[0-9]+)?)\s*(kwh|wh)?$', 3)
                                                                        AS energy_unit,
        TRY_CAST(REGEXP_EXTRACT(peak_text, '^(-?[0-9]+(\.[0-9]+)?)\s*(kw)?$', 1) AS DOUBLE)
                                                                        AS peak_number,
        TRY_CAST(REGEXP_EXTRACT(outage_text, '^(-?[0-9]+(\.[0-9]+)?)\s*(h|hr|hrs|hours)?$', 1)
                 AS DOUBLE)                                             AS outage_number
    FROM standardised
),

-- Step 3: convert units with CASE and keep only believable values.
-- Out-of-range values become NULL; the row itself is kept.
converted AS (
    SELECT
        customer_id,
        reading_date,
        CASE
            WHEN energy_unit = 'wh' THEN energy_number / 1000.0    -- '800 Wh' -> 0.8 kWh
            ELSE energy_number                                     -- 'kwh' or no unit
        END AS energy_kwh_any,
        CASE WHEN peak_number BETWEEN 0 AND 20 THEN peak_number END     AS peak_load_kw,
        CASE WHEN outage_number BETWEEN 0 AND 24 THEN outage_number END AS outage_hours
    FROM parsed
),

-- Step 4: de-duplicate with ROW_NUMBER. Some readings were sent twice: exact copies,
-- and copies with the values left blank. Keep the copy with the fewest blanks.
ranked AS (
    SELECT
        customer_id,
        reading_date,
        CASE WHEN energy_kwh_any >= 0 THEN energy_kwh_any END AS energy_kwh,   -- negative -> NULL
        peak_load_kw,
        outage_hours,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id, reading_date
            ORDER BY
                CAST(energy_kwh_any IS NULL AS INTEGER)
                + CAST(peak_load_kw IS NULL AS INTEGER)
                + CAST(outage_hours IS NULL AS INTEGER),
                energy_kwh_any, peak_load_kw, outage_hours
        ) AS copy_number
    FROM converted
    WHERE customer_id IS NOT NULL
      AND reading_date IS NOT NULL
)

SELECT customer_id, reading_date, energy_kwh, peak_load_kw, outage_hours
FROM ranked
WHERE copy_number = 1;
