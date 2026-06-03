{{ config(materialized='view') }}

SELECT
    rating_id,
    order_id,
    user_id,
    rider_id,
    outlet_id,
    user_rating_for_food,
    user_rating_for_rider,
    user_comment,
    outlet_rating_for_user,
    rider_rating_for_user,
    rating_timestamp,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'ratings') }}
