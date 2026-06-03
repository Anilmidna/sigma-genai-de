{{ config(materialized='view') }}

SELECT
    user_id,
    full_name,
    registered_email,
    mobile_number,
    home_address,
    home_lat,
    home_lng,
    office_address,
    office_lat,
    office_lng,
    date_of_birth,
    device_id,
    signup_date,
    last_active_at,
    total_orders,
    wallet_balance,
    preferred_payment,
    is_premium,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'users') }}
WHERE user_id IS NOT NULL
