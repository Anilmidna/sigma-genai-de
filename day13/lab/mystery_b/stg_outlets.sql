{{ config(materialized='view') }}

SELECT
    outlet_id,
    outlet_name,
    cuisine_type,
    owner_name,
    owner_mobile,
    owner_email,
    fssai_number,
    gst_number,
    outlet_address,
    outlet_lat,
    outlet_lng,
    avg_prep_time_mins,
    avg_rating,
    is_pure_veg,
    accepts_cash,
    commission_pct,
    onboarded_date,
    is_active,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'outlets') }}
