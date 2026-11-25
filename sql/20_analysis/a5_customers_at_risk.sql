-- =============================================================================
-- a5: Customers at risk: used energy in the last 14 days of data but made no
--     (counted) payment in that time.
-- "Last 14 days" is measured from the last date in the data, not from today,
-- so the query gives the same answer whenever it is run.
-- =============================================================================
WITH last_day AS (
    SELECT MAX(date) AS last_date FROM customer_daily
),
recent AS (
    SELECT
        d.customer_id,
        d.community,
        d.plan_name,
        SUM(d.energy_kwh)           AS kwh_last_14_days,
        SUM(d.energy_cost_ngn)      AS cost_last_14_days_ngn,
        SUM(d.amount_paid_ngn)      AS paid_last_14_days_ngn
    FROM customer_daily AS d
    CROSS JOIN last_day AS l
    -- DATE minus a whole number gives a DATE in both DuckDB and PostgreSQL.
    WHERE d.date > l.last_date - 14
    GROUP BY d.customer_id, d.community, d.plan_name
),
last_payment AS (
    SELECT customer_id, MAX(date) AS last_payment_date
    FROM customer_daily
    WHERE payment_count > 0
    GROUP BY customer_id
)
SELECT
    r.customer_id,
    r.community,
    r.plan_name,
    ROUND(r.kwh_last_14_days, 1)            AS kwh_last_14_days,
    ROUND(r.cost_last_14_days_ngn, 0)       AS cost_last_14_days_ngn,
    p.last_payment_date,
    l.last_date - p.last_payment_date       AS days_since_last_payment
FROM recent AS r
CROSS JOIN last_day AS l
LEFT JOIN last_payment AS p ON p.customer_id = r.customer_id
WHERE r.kwh_last_14_days > 0
  AND r.paid_last_14_days_ngn = 0
ORDER BY r.cost_last_14_days_ngn DESC;
