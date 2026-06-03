{{ config(materialized='view') }}

SELECT
    rider_id,
    full_name,
    mobile_number,
    email,
    date_of_birth,
    dl_number,
    dl_expiry_date,
    vehicle_number,
    vehicle_type,
    bank_account_number,
    ifsc_code,
    home_address,
    current_lat,
    current_lng,
    onboarding_date,
    background_check_status,
    is_available,
    total_deliveries,
    avg_rating,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'riders') }}
WHERE rider_id IS NOT NULL
