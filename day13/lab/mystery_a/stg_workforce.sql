{{ config(materialized='view') }}

SELECT
    emp_id,
    emp_code,
    first_name,
    last_name,
    personal_email,
    mobile_number,
    date_of_birth,
    gender,
    home_address,
    emergency_contact_name,
    emergency_contact_phone,
    pan_number,
    uan_number,
    pf_account_number,
    bank_account_number,
    ifsc_code,
    joining_date,
    department_id,
    designation_id,
    reporting_mgr_id,
    employment_type,
    work_location,
    is_active,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM {{ source('raw', 'workforce') }}
WHERE emp_id IS NOT NULL
