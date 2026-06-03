{{ config(materialized='table') }}

SELECT
    department_id,
    work_location,
    employment_type,
    grade_band,
    COUNT(emp_id)                                           AS headcount,
    COUNT(CASE WHEN is_active THEN 1 END)                  AS active_count,
    AVG(DATEDIFF('day', joining_date, CURRENT_DATE()))      AS avg_tenure_days,
    COUNT(CASE WHEN employment_type = 'CONTRACT' THEN 1 END) AS contractor_count
FROM {{ ref('stg_workforce') }}
GROUP BY 1, 2, 3, 4
