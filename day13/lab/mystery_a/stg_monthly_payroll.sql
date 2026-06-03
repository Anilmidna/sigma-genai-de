{{ config(materialized='view') }}

SELECT
    payroll_id,
    emp_id,
    payroll_month,
    working_days,
    present_days,
    lop_days,
    gross_earnings,
    basic_pay,
    hra_paid,
    special_allowance_paid,
    overtime_amount,
    performance_bonus,
    tds_deducted,
    pf_deducted,
    esi_deducted,
    pt_deducted,
    loan_recovery,
    net_take_home,
    payment_status,
    payment_date,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'monthly_payroll') }}
