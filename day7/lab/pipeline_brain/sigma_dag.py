from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging
import json

default_args = {
    'owner': 'data-engineering',
   'retries': 2,
   'retry_delay': timedelta(minutes=5),
    'email_on_failure': True,
}

def on_failure_callback(context):
    """Logs failure details."""
    dag_id = context['dag'].dag_id
    task_id = context['task_instance'].task_id
    execution_date = context['execution_date']
    error_message = context['exception']
    logging.error(f"DAG: {dag_id}, Task: {task_id}, Execution Date: {execution_date}, Error: {error_message}")

def sla_miss_callback(context):
    """Sends alert for SLA miss."""
    dag_id = context['dag'].dag_id
    execution_date = context['execution_date']
    logging.warning(f"DAG: {dag_id}, Execution Date: {execution_date} has missed SLA")

def extract_bronze(**context):
    """Ingest raw CSVs to Bronze Parquet."""
    ti = context['task_instance']
    ti.xcom_push(key='bronze_path', value='/path/to/bronze/parquet')
    logging.info(f"{ti} - Bronze layer ingested successfully.")

def transform_silver(**context):
    """Clean, enrich, deduplicate to Silver."""
    ti = context['task_instance']
    bronze_path = context['ti'].xcom_pull(task_ids='extract_bronze', key='bronze_path')
    # Transformation logic here
    ti.xcom_push(key='silver_path', value='/path/to/silver/parquet')
    logging.info(f"{ti} - Silver layer transformed successfully.")

def build_gold(**context):
    """Generate the 3 Gold aggregation tables."""
    ti = context['task_instance']
    silver_path = context['ti'].xcom_pull(task_ids='transform_silver', key='silver_path')
    # Aggregation logic here
    logging.info(f"{ti} - Gold layer built successfully.")

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
        on_failure_callback=on_failure_callback,
    )

    transform_silver_task = PythonOperator(
        task_id='transform_silver',
        python_callable=transform_silver,
        on_failure_callback=on_failure_callback,
    )

    build_gold_task = PythonOperator(
        task_id='build_gold',
        python_callable=build_gold,
        on_failure_callback=on_failure_callback,
    )

    extract_bronze_task >> transform_silver_task >> build_gold_task
