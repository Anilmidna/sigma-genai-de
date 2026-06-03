{{ config(materialized='view') }}

SELECT
    order_id,
    user_id,
    outlet_id,
    rider_id,
    order_placed_at,
    order_confirmed_at,
    picked_up_at,
    delivered_at,
    delivery_address,
    drop_lat,
    drop_lng,
    item_total,
    delivery_fee,
    platform_discount,
    final_amount_paid,
    payment_method,
    promo_code_used,
    surge_multiplier,
    otp_verified,
    order_status,
    cancellation_reason,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'orders') }}
WHERE order_id IS NOT NULL
