-- =============================================================================
-- a3: Top 10 customers by total consumption, using RANK().
-- RANK gives tied customers the same rank (and then skips numbers), so the
-- result can hold more than 10 rows if there is a tie at 10th place.
-- =============================================================================
WITH totals AS (
    SELECT
        customer_id,
        community,
        plan_name,
        household_band,
        ROUND(SUM(energy_kwh), 1)       AS total_kwh,
        COUNT(energy_kwh)               AS days_with_reading
    FROM customer_daily
    GROUP BY customer_id, community, plan_name, household_band
),
ranked AS (
    SELECT
        RANK() OVER (ORDER BY total_kwh DESC) AS consumption_rank,
        *
    FROM totals
)
SELECT *
FROM ranked
WHERE consumption_rank <= 10
ORDER BY consumption_rank, customer_id;
