-- stg_events.sql
-- Staging: user behaviour events from mobile app analytics

{{ config(materialized='view') }}

SELECT
    event_id,
    customer_id,
    event_type,
    event_timestamp,
    session_id,
    device_type,
    os_version,
    app_version,
    screen_name,
    latitude,
    longitude,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'events') }}
WHERE event_id IS NOT NULL
