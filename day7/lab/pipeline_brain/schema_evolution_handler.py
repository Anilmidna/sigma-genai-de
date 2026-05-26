from typing import Dict, List, Tuple, Union
import pyspark.sql.functions as F
from pyspark.sql import DataFrame
from pyspark.sql.types import StructType, StructField, StringType, FloatType, IntegerType

def detect_schema_drift(expected_schema: Dict[str, str], actual_schema: Dict[str, str]) -> Dict[str, Union[Dict[str, str], List[str], Dict[str, Tuple[str, str]], str]]:
    """
    Detects schema drift between expected and actual schemas.

    Args:
    expected_schema (Dict[str, str]): The expected schema.
    actual_schema (Dict[str, str]): The actual schema.

    Returns:
    Dict[str, Union[Dict[str, str], List[str], Dict[str, Tuple[str, str]], str]]: A dictionary containing new columns, removed columns, type changes, and drift severity.
    """
    new_columns = {k: v for k, v in actual_schema.items() if k not in expected_schema}
    removed_columns = {k: v for k, v in expected_schema.items() if k not in actual_schema}
    type_changes = {k: (expected_schema[k], actual_schema[k]) for k in expected_schema if expected_schema[k]!= actual_schema[k]}
    drift_severity = 'NONE'
    if new_columns:
        if any(actual_schema[col] not in ['string', 'float'] or not (actual_schema[col] == 'float' and expected_schema.get(col, '').startswith('float')) for col in new_columns):
            drift_severity = 'HIGH' if any(actual_schema[col]!='string' for col in new_columns) else 'LOW'
        else:
            drift_severity = 'LOW'
    if removed_columns:
        drift_severity = 'BREAKING'
    return {'new_columns': new_columns, 'removed_columns': list(removed_columns.keys()), 'type_changes': type_changes, 'drift_severity': drift_severity}

def decide_action(drift_report: Dict[str, Union[Dict[str, str], List[str], Dict[str, Tuple[str, str]], str]]) -> Dict[str, Dict[str, Union[str, str, str]]]:
    """
    Decides the action to take for each column based on the drift report.

    Args:
    drift_report (Dict[str, Union[Dict[str, str], List[str], Dict[str, Tuple[str, str]], str]]): The drift report.

    Returns:
    Dict[str, Dict[str, Union[str, str, str]]]: A dictionary containing the action, reason, and risk level for each column.
    """
    decisions = {}
    for col, dtype in drift_report['new_columns'].items():
        if dtype =='string':
            decisions[col] = {'action': 'ADD_TO_SCHEMA','reason': 'New nullable string column', 'risk_level': 'LOW'}
        elif dtype == 'float':
            decisions[col] = {'action': 'FLAG_ANOMALY','reason': 'New float column affecting revenue calculations', 'risk_level': 'HIGH'}
    for col in drift_report['removed_columns']:
        decisions[col] = {'action': 'HALT','reason': 'Removed column will break downstream queries', 'risk_level': 'BREAKING'}
    for col, (old_type, new_type) in drift_report['type_changes'].items():
        if new_type == 'float' and old_type == 'int':
            decisions[col] = {'action': 'ADD_TO_SCHEMA','reason': 'Type widening from int to float', 'risk_level': 'LOW'}
        elif new_type == 'int' and old_type == 'float':
            decisions[col] = {'action': 'FLAG_ANOMALY','reason': 'Type narrowing from float to int', 'risk_level': 'HIGH'}
    return decisions

def apply_schema_evolution(spark_df: DataFrame, decisions: Dict[str, Dict[str, Union[str, str, str]]], updated_schema: Dict[str, str]) -> Tuple[DataFrame, List[str]]:
    """
    Applies the schema evolution decisions to the DataFrame.

    Args:
    spark_df (DataFrame): The DataFrame to evolve.
    decisions (Dict[str, Dict[str, Union[str, str, str]]]): The decisions to apply.
    updated_schema (Dict[str, str]): The updated schema.

    Returns:
    Tuple[DataFrame, List[str]]: The evolved DataFrame and a list of migration notes.
    """
    migration_notes = []
    for col, decision in decisions.items():
        if decision['action'] == 'DROP_SILENTLY':
            spark_df = spark_df.drop(col)
        elif decision['action'] == 'ADD_TO_SCHEMA':
            migration_notes.append(f"Added column '{col}' to schema.")
        elif decision['action'] == 'FLAG_ANOMALY':
            spark_df = spark_df.withColumn(f"{col}_anomaly", F.when(F.col(col).isNull(), F.lit(True)).otherwise(F.lit(False)))
            migration_notes.append(f"Flagged anomalies in column '{col}'.")
    return spark_df, migration_notes

def handle_drift(expected_schema: Dict[str, str], actual_schema: Dict[str, str], spark_df: DataFrame = None) -> Dict[str, Union[Dict[str, Union[Dict[str, Union[str, str, str]]]], Dict[str, Union[Dict[str, str], List[str], Dict[str, Tuple[str, str]], str]], List[str]]]:
    """
    Handles schema drift by detecting, deciding, and applying schema evolution.

    Args:
    expected_schema (Dict[str, str]): The expected schema.
    actual_schema (Dict[str, str]): The actual schema.
    spark_df (DataFrame, optional): The DataFrame to evolve. Defaults to None.

    Returns:
    Dict[str, Union[Dict[str, Union[Dict[str, Union[str, str, str]]]], Dict[str, Union[Dict[str, str], List[str], Dict[str, Tuple[str, str]], str]], List[str]]]: The full evolution report.
    """
    drift_report = detect_schema_drift(expected_schema, actual_schema)
    decisions = decide_action(drift_report)
    if spark_df is not None:
        evolved_df, migration_notes = apply_schema_evolution(spark_df, decisions, {**expected_schema, **{k: v for k, v in actual_schema.items() if k not in expected_schema}})
        return {'evolution_report': {'drift_report': drift_report, 'decisions': decisions}, 'evolved_df': evolved_df,'migration_notes': migration_notes}
    else:
        print(f"Drift Report: {drift_report}")
        print(f"Decisions: {decisions}")
        return {'evolution_report': {'drift_report': drift_report, 'decisions': decisions}}
