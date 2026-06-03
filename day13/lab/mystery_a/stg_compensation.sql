{{ config(materialized='view') }}

SELECT
    emp_id,
    effective_date,
    basic_ctc,
    hra_amount,
    special_allowance,
    gross_ctc,
    employer_pf_contribution,
    employer_esi_contribution,
    grade_band,
    salary_revision_reason,
    approved_by_mgr_id,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'compensation') }}
WHERE emp_id IS NOT NULL
