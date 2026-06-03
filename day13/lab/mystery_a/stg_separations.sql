{{ config(materialized='view') }}

SELECT
    separation_id,
    emp_id,
    separation_type,
    resignation_date,
    last_working_date,
    exit_interview_done,
    exit_reason_category,
    exit_reason_detail,
    rehire_eligible,
    full_final_amount,
    full_final_status,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'separations') }}
