{{ config(materialized='table') }}

SELECT
    o.user_id,
    COUNT(o.order_id)                                           AS total_orders,
    AVG(o.final_amount_paid)                                    AS avg_order_value,
    MAX(o.order_placed_at)                                      AS last_order_at,
    COUNT(DISTINCT o.outlet_id)                                 AS unique_outlets,
    MODE(o.payment_method)                                      AS preferred_payment,
    AVG(EXTRACT(HOUR FROM o.order_placed_at))                   AS avg_order_hour,
    COUNT(CASE WHEN o.order_status = 'CANCELLED' THEN 1 END)    AS cancelled_orders,
    SUM(o.platform_discount)                                    AS total_discount_availed,
    AVG(r.user_rating_for_food)                                 AS avg_food_rating_given
FROM {{ ref('stg_orders') }} o
LEFT JOIN {{ ref('stg_ratings') }} r ON o.order_id = r.order_id
GROUP BY 1
