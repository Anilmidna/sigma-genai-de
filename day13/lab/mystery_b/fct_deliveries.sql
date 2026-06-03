{{ config(materialized='incremental', unique_key='order_id') }}

SELECT
    o.order_id,
    DATE(o.order_placed_at)                                     AS order_date,
    o.user_id,
    o.outlet_id,
    out.cuisine_type,
    o.rider_id,
    o.item_total,
    o.delivery_fee,
    o.platform_discount,
    o.final_amount_paid,
    o.surge_multiplier,
    DATEDIFF('minute', o.picked_up_at, o.delivered_at)          AS actual_delivery_mins,
    DATEDIFF('minute', o.order_placed_at, o.delivered_at)       AS total_fulfilment_mins,
    o.order_status,
    COALESCE(r.user_rating_for_food, 0)                         AS food_rating,
    COALESCE(r.user_rating_for_rider, 0)                        AS rider_rating,
    o._loaded_at
FROM {{ ref('stg_orders') }} o
JOIN {{ ref('stg_outlets') }} out ON o.outlet_id = out.outlet_id
LEFT JOIN {{ ref('stg_ratings') }} r ON o.order_id = r.order_id

{% if is_incremental() %}
WHERE o._loaded_at > (SELECT MAX(_loaded_at) FROM {{ this }})
{% endif %}
