-- =============================================================================
-- 10_daily_customer.sql  ->  view: customer_daily
-- One row per customer per day, wherever the customer had a meter reading OR
-- a payment. Built from the four clean views with CTEs and three deliberate joins.
-- =============================================================================
CREATE OR REPLACE VIEW customer_daily AS

-- Payments rolled up to one row per customer per day.
-- Only payments that are definitely NOT reversed are counted.
-- (is_reversed = FALSE is never true for NULL, so unknown flags are left out.)
WITH daily_payments AS (
    SELECT
        customer_id,
        payment_date        AS date,
        SUM(amount_ngn)     AS amount_paid_ngn,
        COUNT(*)            AS payment_count
    FROM clean_payments
    WHERE is_reversed = FALSE
    GROUP BY customer_id, payment_date
),

-- FULL OUTER JOIN: a customer-day belongs here if there was a reading OR a payment.
-- COALESCE takes the key from whichever side exists.
readings_and_payments AS (
    SELECT
        COALESCE(r.customer_id, p.customer_id)  AS customer_id,
        COALESCE(r.reading_date, p.date)        AS date,
        r.energy_kwh,
        r.peak_load_kw,
        r.outage_hours,
        p.amount_paid_ngn,
        p.payment_count
    FROM clean_meter_readings AS r
    FULL OUTER JOIN daily_payments AS p
        ON  p.customer_id = r.customer_id
        AND p.date        = r.reading_date
),

-- Filling a missing value FROM ANOTHER TABLE using a business rule.
-- Business rule (an assumption for this project): a customer with no plan on file is
-- billed on the Basic plan. The Basic plan's ID is looked up in clean_tariff_plans
-- rather than typed in, so a renamed ID would still be found.
customers_with_plan AS (
    SELECT
        c.customer_id,
        c.community,
        c.household_band,
        COALESCE(
            c.plan_id,
            (SELECT t.plan_id FROM clean_tariff_plans AS t WHERE t.plan_name = 'Basic')
        )                       AS plan_id,
        c.plan_id IS NULL       AS plan_was_defaulted
    FROM clean_customers AS c
)

SELECT
    rp.customer_id,
    rp.date,
    c.community,
    c.household_band,
    t.plan_name,
    c.plan_was_defaulted,
    rp.energy_kwh,
    rp.peak_load_kw,
    rp.outage_hours,
    rp.energy_kwh * t.price_per_kwh                     AS energy_cost_ngn,   -- NULL if either is NULL
    COALESCE(rp.amount_paid_ngn, 0)                     AS amount_paid_ngn,   -- business default: 0
    COALESCE(rp.payment_count, 0)                       AS payment_count,
    CASE WHEN COALESCE(rp.payment_count, 0) > 0
         THEN 'Paid' ELSE 'No payment' END              AS payment_status
FROM readings_and_payments AS rp
-- INNER JOIN: drop customer-days for IDs not in the customer list (orphan payments).
INNER JOIN customers_with_plan AS c
    ON c.customer_id = rp.customer_id
-- LEFT JOIN: a plan ID missing from the tariff list must not drop the row.
LEFT JOIN clean_tariff_plans AS t
    ON t.plan_id = c.plan_id;
