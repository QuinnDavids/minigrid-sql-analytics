-- =============================================================================
-- a2: Revenue collected compared with the cost of energy consumed,
--     per plan, per month.
-- collection_rate_pct = revenue / cost x 100. Below 100 means customers used more
-- than they paid for that month.
-- =============================================================================
WITH monthly AS (
    SELECT
        plan_name,
        CAST(DATE_TRUNC('month', date) AS DATE)     AS month,
        SUM(energy_cost_ngn)                        AS cost_of_energy_ngn,
        SUM(amount_paid_ngn)                        AS revenue_collected_ngn
    FROM customer_daily
    GROUP BY plan_name, CAST(DATE_TRUNC('month', date) AS DATE)
)
SELECT
    plan_name,
    month,
    ROUND(cost_of_energy_ngn, 0)                            AS cost_of_energy_ngn,
    ROUND(revenue_collected_ngn, 0)                         AS revenue_collected_ngn,
    ROUND(revenue_collected_ngn - cost_of_energy_ngn, 0)    AS surplus_ngn,
    -- NULLIF avoids dividing by zero if a month had no measurable consumption.
    ROUND(100.0 * revenue_collected_ngn / NULLIF(cost_of_energy_ngn, 0), 1)
                                                            AS collection_rate_pct
FROM monthly
ORDER BY plan_name, month;
