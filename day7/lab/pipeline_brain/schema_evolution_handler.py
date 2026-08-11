from typing import Dict, List, Tuple, Union
import pyspark.sql.functions as F
from pyspark.sql import DataFrame

def detect_schema_drift(expected_schema: Dict[str, str], actual_schema: Dict[str, str]) -> Dict[str, Union[Dict[str, str], str, bool]]:
    new_columns = {k: v for k, v in actual_schema.items() if k not in expected_schema}
    removed_columns = {k: v for k, v in expected_schema.items() if k not in actual_schema}
    type_changes = {k: (expected_schema[k], actual_schema[k]) for k in expected_schema if expected_schema[k]!= actual_schema[k]}
    has_drift = bool(new_columns or removed_columns or type_changes)

    drift_severity = 'NONE'
    if new_columns:
        if all('null' in v for v in new_columns.values()):
            drift_severity = 'LOW'
        else:
            drift_severity = 'HIGH'
    if removed_columns:
        drift_severity = 'BREAKING'
    if type_changes:
        drift_severity = 'HIGH' if drift_severity!= 'BREAKING' else drift_severity

    return {
        'new_columns': new_columns,
       'removed_columns': removed_columns,
        'type_changes': type_changes,
        'has_drift': has_drift,
        'drift_severity': drift_severity
    }

def decide_action(drift_report: Dict[str, Union[Dict[str, str], Dict[str, Union[str, str]], str, bool]]) -> Dict[str, Dict[str, str]]:
    decisions = {}
    for column, dtype in drift_report['new_columns'].items():
        if dtype.endswith('null'):
            decisions[column] = {'action': 'ADD_TO_SCHEMA', 'reason': 'New nullable column', 'risk_level': 'LOW'}
        elif dtype == 'float' or dtype == 'double':
            decisions[column] = {'action': 'FLAG_ANOMALY','reason': 'New numeric column', 'risk_level': 'HIGH'}
        else:
            decisions[column] = {'action': 'ADD_TO_SCHEMA','reason': 'New string column', 'risk_level': 'LOW'}
    for column, (old_type, new_type) in drift_report['type_changes'].items():
        if new_type.endswith('null') and old_type!= new_type:
            decisions[column] = {'action': 'ADD_TO_SCHEMA','reason': f'Type widened from {old_type} to {new_type}', 'risk_level': 'LOW'}
        elif old_type!= new_type:
            decisions[column] = {'action': 'FLAG_ANOMALY','reason': f'Type narrowed from {old_type} to {new_type}', 'risk_level': 'HIGH'}
    for column in drift_report['removed_columns']:
        decisions[column] = {'action': 'HALT','reason': 'Removed column', 'risk_level': 'BREAKING'}
    return decisions

def apply_schema_evolution(spark_df: DataFrame, decisions: Dict[str, Dict[str, str]], updated_schema: Dict[str, str]) -> Tuple[DataFrame, List[str]]:
    migration_notes = []
    for column, decision in decisions.items():
        if decision['action'] == 'DROP_SILENTLY':
            spark_df = spark_df.drop(column)
        elif decision['action'] == 'FLAG_ANOMALY':
            spark_df = spark_df.withColumn(f'{column}_anomaly', F.when(F.col(column).isNull(), F.lit(True)).otherwise(F.lit(False)))
            migration_notes.append(f'Column {column} flagged for anomaly due to potential impact on calculations.')
        elif decision['action'] == 'ADD_TO_SCHEMA':
            if column not in spark_df.columns:
                spark_df = spark_df.withColumn(column, F.lit(None).cast(updated_schema[column]))
                migration_notes.append(f'Column {column} added to schema with data type {updated_schema[column]}.')
    return spark_df, migration_notes

def handle_drift(expected_schema: Dict[str, str], actual_schema: Dict[str, str], spark_df: DataFrame = None) -> Dict[str, Union[Dict[str, Union[Dict[str, str], List[str]]], Dict[str, Union[Dict[str, str], Dict[str, Union[str, str]], str, bool]]]]:
    drift_report = detect_schema_drift(expected_schema, actual_schema)
    if not drift_report['has_drift']:
        print("No schema drift detected.")
        return {'drift_report': drift_report}
    
    decisions = decide_action(drift_report)
    if spark_df is not None:
        evolved_df, migration_notes = apply_schema_evolution(spark_df, decisions, {**expected_schema, **actual_schema})
        print("Schema evolution applied successfully.")
        return {'drift_report': drift_report, 'decisions': decisions,'migration_notes': migration_notes}
    else:
        print("Schema evolution decisions made without applying to DataFrame.")
        return {'drift_report': drift_report, 'decisions': decisions}
