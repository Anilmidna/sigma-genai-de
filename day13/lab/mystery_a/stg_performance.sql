{{ config(materialized='view') }}

SELECT
    review_id,
    emp_id,
    review_cycle,
    reviewer_emp_id,
    self_rating,
    manager_rating,
    final_rating,
    rating_label,
    strengths_comment,
    improvement_areas,
    promotion_recommended,
    pip_initiated,
    review_status,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'performance_reviews') }}
