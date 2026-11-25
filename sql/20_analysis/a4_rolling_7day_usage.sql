-- =============================================================================
-- a4: Rolling 7-day average energy use per customer, using a window frame.
--
-- RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW means "this day and the
-- six calendar days before it". RANGE (calendar days) is used instead of ROWS
-- (the previous 6 rows) because some days have no reading: with ROWS, a gap would
-- stretch the window further back than 7 days. AVG ignores days with no value.
-- =============================================================================
SELECT
    customer_id,
    date,
    energy_kwh,
    ROUND(
        AVG(energy_kwh) OVER (
            PARTITION BY customer_id
            ORDER BY date
            RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW
        ),
        2
    )                                           AS rolling_7day_avg_kwh,
    COUNT(energy_kwh) OVER (
        PARTITION BY customer_id
        ORDER BY date
        RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW
    )                                           AS readings_in_window
FROM customer_daily
ORDER BY customer_id, date;
