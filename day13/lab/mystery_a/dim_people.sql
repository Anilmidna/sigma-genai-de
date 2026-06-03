{{ config(materialized='table') }}

-- PII masked for analytics use
-- Raw PII (pan, bank account, mobile) excluded — access requires stg_workforce
SELECT
    w.emp_id,
    w.emp_code,
    w.department_id,
    w.designation_id,
    w.grade_band,
    w.employment_type,
    w.work_location,
    w.joining_date,
    w.is_active,
    DATEDIFF('year', w.date_of_birth, CURRENT_DATE())       AS age_band,
    DATEDIFF('day',  w.joining_date,  CURRENT_DATE())       AS tenure_days,
    COALESCE(perf.final_rating, 'NOT_REVIEWED')             AS latest_rating,
    COALESCE(perf.promotion_recommended, FALSE)             AS promotion_flag,
    SHA2(w.personal_email, 256)                             AS email_hash,
    SHA2(w.pan_number, 256)                                 AS pan_hash,
    w._loaded_at
FROM {{ ref('stg_workforce') }} w
LEFT JOIN {{ ref('stg_performance') }} perf
    ON w.emp_id = perf.emp_id
    AND perf.review_cycle = (
        SELECT MAX(review_cycle)
        FROM {{ ref('stg_performance') }}
        WHERE emp_id = w.emp_id
    )
