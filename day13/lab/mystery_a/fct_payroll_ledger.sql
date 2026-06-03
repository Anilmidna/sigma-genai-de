{{ config(materialized='incremental', unique_key='payroll_id') }}

SELECT
    p.payroll_id,
    p.payroll_month,
    p.emp_id,
    w.department_id,
    w.work_location,
    w.employment_type,
    c.grade_band,
    p.gross_earnings,
    p.net_take_home,
    p.tds_deducted,
    p.pf_deducted,
    p.performance_bonus,
    p.payment_status,
    p.payment_date,
    p._loaded_at
FROM {{ ref('stg_monthly_payroll') }} p
JOIN {{ ref('stg_workforce') }} w ON p.emp_id = w.emp_id
LEFT JOIN {{ ref('stg_compensation') }} c ON p.emp_id = c.emp_id

{% if is_incremental() %}
WHERE p._loaded_at > (SELECT MAX(_loaded_at) FROM {{ this }})
{% endif %}
