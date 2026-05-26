from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
import logging
import json

default_args = {
    'owner': 'data-engineering',
   'retries': 2,
   'retry_delay': timedelta(minutes=5),
    'email_on_failure': True
}

def on_failure_callback(context):
    dag_id = context['dag'].dag_id
    task_id = context['task'].task_id
    execution_date = context['execution_date']
    error_message = context['exception']
    logging.error(f"Dag: {dag_id}, Task: {task_id}, Execution Date: {execution_date}, Error: {error_message}")

def sla_miss_callback(context):
    dag_id = context['dag'].dag_id
    execution_date = context['execution_date']
    logging.error(f"Dag: {dag_id}, Execution Date: {execution_date}, SLA Miss")

def log_run_metadata(context):
    task_instance = context['task_instance']
    run_metadata = {
        'dag_id': task_instance.dag_id,
        'task_id': task_instance.task_id,
        'execution_date': str(task_instance.execution_date),
        'status': task_instance.current_state().name
    }
    with open('/path/to/metadata.json', 'a') as f:
        json.dump(run_metadata, f)
    f.write('\n')

def extract_bronze(**context):
    logging.info(f"Starting Bronze layer extraction for {context['execution_date']}")
    # Code to read CSVs and write to Bronze Parquet
    logging.info(f"Completed Bronze layer extraction for {context['execution_date']}")
    raise Exception("Simulated failure")  # Remove in production

def transform_silver(**context):
    logging.info(f"Starting Silver layer transformation for {context['execution_date']}")
    # Code to clean, enrich, deduplicate and write to Silver Parquet
    logging.info(f"Completed Silver layer transformation for {context['execution_date']}")
    raise Exception("Simulated failure")  # Remove in production

def build_gold(**context):
    logging.info(f"Starting Gold layer aggregation for {context['execution_date']}")
    # Code to generate Gold aggregation tables
    logging.info(f"Completed Gold layer aggregation for {context['execution_date']}")
    raise Exception("Simulated failure")  # Remove in production

with DAG(
    dag_id='sigma_transaction_pipeline',
    schedule='0 2 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    on_failure_callback=on_failure_callback,
    sla_miss_callback=sla_miss_callback,
    tags=['sigma', 'transactions', 'daily'],
    description="Daily Bronze->Silver->Gold pipeline for Sigma DataTech transactions"
) as dag:

    extract_bronze_task = PythonOperator(
        task_id='extract_bronze',
        python_callable=extract_bronze,
        on_failure_callback=on_failure_callback
    )

    transform_silver_task = PythonOperator(
        task_id='transform_silver',
        python_callable=transform_silver,
        on_failure_callback=on_failure_callback
    )

    build_gold_task = PythonOperator(
        task_id='build_gold',
        python_callable=build_gold,
        on_failure_callback=on_failure_callback
    )

    extract_bronze_task >> transform_silver_task >> build_gold_task

    # Log run metadata after each run
    extract_bronze_task.on_success_callback = log_run_metadata
    transform_silver_task.on_success_callback = log_run_metadata
    build_gold_task.on_success_callback = log_run_metadata
