{{ config(materialized='table') }}

-- PII masked — raw addresses, coordinates, device_id excluded
-- Access to raw location data requires stg_users (Privacy team approval required)
SELECT
    u.user_id,
    u.signup_date,
    u.is_premium,
    u.preferred_payment,
    DATEDIFF('day', u.signup_date, CURRENT_DATE())              AS account_age_days,
    DATEDIFF('year', u.date_of_birth, CURRENT_DATE())           AS age_approx,
    b.total_orders,
    b.avg_order_value,
    b.avg_order_hour,
    b.preferred_payment                                         AS most_used_payment,
    b.cancelled_orders,
    b.total_discount_availed,
    SHA2(u.registered_email, 256)                               AS email_hash,
    SHA2(u.mobile_number, 256)                                  AS phone_hash,
    -- home_lat, home_lng, office_lat, office_lng intentionally excluded
    u._loaded_at
FROM {{ ref('stg_users') }} u
LEFT JOIN {{ ref('int_user_behaviour') }} b ON u.user_id = b.user_id
