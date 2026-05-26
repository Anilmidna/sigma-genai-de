from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging

default_args = {
    'owner': 'data-engineering',
   'retries': 2,
   'retry_delay': timedelta(minutes=5),
    'email_on_failure': True
}

def on_failure_callback(context):
    dag_id = context['dag'].dag_id
    task_id = context['task_instance'].task_id
    execution_date = context['execution_date']
    error_message = context['exception']
    logging.error(f"DAG: {dag_id}, Task: {task_id}, Execution Date: {execution_date}, Error: {error_message}")

def sla_miss_callback(context):
    dag_id = context['dag'].dag_id
    execution_date = context['execution_date']
    logging.warning(f"DAG: {dag_id}, Execution Date: {execution_date}, SLA Miss")

dag = DAG(
    dag_id='sigma_transaction_pipeline',
    schedule='0 2 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    on_failure_callback=on_failure_callback,
    sla_miss_callback=sla_miss_callback,
    tags=['sigma', 'transactions', 'daily'],
    description="Daily Bronze->Silver->Gold pipeline for Sigma DataTech transactions"
)

def extract_bronze(**context):
    """Ingest raw CSVs to Bronze Parquet"""
    logging.info(f"Starting extract_bronze task: {context['task_instance']}")
    # Code to read CSVs and write to Bronze Parquet
    logging.info(f"Completed extract_bronze task: {context['task_instance']}")

def transform_silver(**context):
    """Clean, enrich, deduplicate to Silver"""
    logging.info(f"Starting transform_silver task: {context['task_instance']}")
    # Code to transform data to Silver Parquet
    logging.info(f"Completed transform_silver task: {context['task_instance']}")

def build_gold(**context):
    """Generate the 3 Gold aggregation tables"""
    logging.info(f"Starting build_gold task: {context['task_instance']}")
    # Code to build Gold tables
    logging.info(f"Completed build_gold task: {context['task_instance']}")

extract_bronze_task = PythonOperator(
    task_id='extract_bronze',
    python_callable=extract_bronze,
    on_failure_callback=on_failure_callback,
    dag=dag,
)

transform_silver_task = PythonOperator(
    task_id='transform_silver',
    python_callable=transform_silver,
    on_failure_callback=on_failure_callback,
    dag=dag,
)

build_gold_task = PythonOperator(
    task_id='build_gold',
    python_callable=build_gold,
    on_failure_callback=on_failure_callback,
    dag=dag,
)

extract_bronze_task >> transform_silver_task >> build_gold_task
