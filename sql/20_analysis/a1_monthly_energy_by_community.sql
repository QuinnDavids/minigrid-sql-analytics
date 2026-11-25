-- =============================================================================
-- a1: Monthly energy use per community.
-- Note: the data ends on 28 June, so June is two days short of a full month.
-- =============================================================================
SELECT
    community,
    -- DATE_TRUNC rounds each date down to the first of its month.
    CAST(DATE_TRUNC('month', date) AS DATE)                      AS month,
    COUNT(DISTINCT customer_id)                                   AS customers,
    ROUND(SUM(energy_kwh), 1)                                     AS total_kwh,
    ROUND(SUM(energy_kwh) / COUNT(DISTINCT customer_id), 1)       AS kwh_per_customer
FROM customer_daily
GROUP BY community, CAST(DATE_TRUNC('month', date) AS DATE)
ORDER BY community, month;
