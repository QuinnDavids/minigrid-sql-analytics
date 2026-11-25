-- =============================================================================
-- a6: Number of distinct customers per plan.
-- COUNT(DISTINCT customer_id) counts each customer once, however many days
-- they appear in customer_daily.
-- =============================================================================
SELECT
    plan_name,
    COUNT(DISTINCT customer_id)                                         AS customers,
    COUNT(DISTINCT CASE WHEN plan_was_defaulted THEN customer_id END)   AS customers_defaulted_to_plan,
    ROUND(SUM(energy_kwh), 0)                                           AS total_kwh,
    ROUND(SUM(amount_paid_ngn), 0)                                      AS total_paid_ngn
FROM customer_daily
GROUP BY plan_name
ORDER BY customers DESC;
