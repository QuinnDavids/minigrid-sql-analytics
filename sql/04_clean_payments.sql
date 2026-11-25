-- =============================================================================
-- 04_clean_payments.sql  ->  view: clean_payments
-- One row per payment. Reads naira in any format, standardises channel names
-- and turns the reversed flag into TRUE / FALSE / NULL (unknown).
-- =============================================================================
CREATE OR REPLACE VIEW clean_payments AS

WITH standardised AS (
    SELECT
        clean_id(payment_id)                AS payment_id,
        clean_id(customer_id)               AS customer_id,
        parse_date(payment_date)            AS payment_date,

        -- '₦5,000', 'N5,000', 'NGN 5000', '5000.00' -> 5000. Zero or less -> NULL.
        CASE WHEN parse_naira(amount) > 0 THEN parse_naira(amount) END AS amount_ngn,

        -- Squeeze spaces and lower-case, then map each spelling to one official name.
        CASE LOWER(REGEXP_REPLACE(clean_text(channel), '\s+', ' ', 'g'))
            WHEN 'ussd'          THEN 'USSD'
            WHEN 'bank transfer' THEN 'Bank Transfer'
            WHEN 'pos'           THEN 'POS'
            WHEN 'card'          THEN 'Card'
        END                                 AS channel,     -- anything else -> NULL

        -- STRICT boolean: only known spellings count. '' or 'maybe' -> NULL,
        -- because guessing could overstate revenue.
        CASE
            WHEN LOWER(clean_text(is_reversed)) IN ('y', 'yes', 'true', 't', '1') THEN TRUE
            WHEN LOWER(clean_text(is_reversed)) IN ('n', 'no', 'false', 'f', '0') THEN FALSE
            ELSE NULL
        END                                 AS is_reversed
    FROM raw_payments
),

-- De-duplicate on payment_id with ROW_NUMBER (keeps the most complete copy).
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY payment_id
            ORDER BY CAST(amount_ngn IS NULL AS INTEGER) + CAST(is_reversed IS NULL AS INTEGER),
                     payment_date
        ) AS copy_number
    FROM standardised
    WHERE payment_id IS NOT NULL
      AND customer_id IS NOT NULL
      AND payment_date IS NOT NULL
)

SELECT payment_id, customer_id, payment_date, amount_ngn, channel, is_reversed
FROM ranked
WHERE copy_number = 1;
