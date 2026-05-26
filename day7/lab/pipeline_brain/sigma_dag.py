from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging
import json

# Default arguments for the DAG
default_args = {
    'owner': 'data-engineering',
   'retries': 2,
   'retry_delay': timedelta(minutes=5),
    'email_on_failure': True,
}

# Initialize the DAG
dag = DAG(
    dag_id='sigma_transaction_pipeline',
    default_args=default_args,
    schedule='0 2 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    sla_miss_callback=lambda context: logging.warning(
        f"SLA miss for DAG {context['dag'].dag_id} at {context['execution_date']}"
    ),
    on_failure_callback=lambda context: logging.error(
        f"Failure in DAG {context['dag'].dag_id}, Task {context['task_instance'].task_id} at {context['execution_date']}: {context['exception']}"
    ),
    tags=['sigma', 'transactions', 'daily'],
    description="Daily Bronze->Silver->Gold pipeline for Sigma DataTech transactions"
)

def extract_bronze(**context):
    """Ingest raw CSVs to Bronze Parquet."""
    logging.info(f"Starting extract_bronze task at {context['execution_date']}")
    # Add code to read CSVs and write to Bronze Parquet
    logging.info(f"Completed extract_bronze task at {context['execution_date']}")

def transform_silver(**context):
    """Clean, enrich, deduplicate to Silver."""
    logging.info(f"Starting transform_silver task at {context['execution_date']}")
    # Add code to transform data to Silver Parquet
    logging.info(f"Completed transform_silver task at {context['execution_date']}")

def build_gold(**context):
    """Generate the 3 Gold aggregation tables."""
    logging.info(f"Starting build_gold task at {context['execution_date']}")
    # Add code to build Gold tables
    logging.info(f"Completed build_gold task at {context['execution_date']}")

# Define tasks
extract_bronze_task = PythonOperator(
    task_id='extract_bronze',
    python_callable=extract_bronze,
    on_failure_callback=lambda context: logging.error(
        f"Failure in extract_bronze task at {context['execution_date']}: {context['exception']}"
    ),
    dag=dag,
)

transform_silver_task = PythonOperator(
    task_id='transform_silver',
    python_callable=transform_silver,
    on_failure_callback=lambda context: logging.error(
        f"Failure in transform_silver task at {context['execution_date']}: {context['exception']}"
    ),
    dag=dag,
)

build_gold_task = PythonOperator(
    task_id='build_gold',
    python_callable=build_gold,
    on_failure_callback=lambda context: logging.error(
        f"Failure in build_gold task at {context['execution_date']}: {context['exception']}"
    ),
    dag=dag,
)

# Set task dependencies
extract_bronze_task >> transform_silver_task >> build_gold_task
