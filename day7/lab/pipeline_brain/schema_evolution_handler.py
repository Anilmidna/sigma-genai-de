from typing import Dict, List, Tuple, Any
import pyspark.sql.functions as F

def detect_schema_drift(expected_schema: Dict[str, str], actual_schema: Dict[str, str]) -> Dict[str, Any]:
    new_columns = {k: v for k, v in actual_schema.items() if k not in expected_schema}
    removed_columns = {k: v for k, v in expected_schema.items() if k not in actual_schema}
    type_changes = {k: (expected_schema[k], actual_schema[k]) for k in expected_schema if expected_schema[k]!= actual_schema[k]}
    drift_severity = 'NONE'
    if new_columns:
        if any(actual_schema[col] not in ['float','string'] or 'NULLABLE' not in actual_schema[col] for col in new_columns):
            drift_severity = 'HIGH'
        else:
            drift_severity = 'LOW'
    if removed_columns:
        drift_severity = 'BREAKING'
    return {
        'new_columns': new_columns,
       'removed_columns': removed_columns,
        'type_changes': type_changes,
        'drift_severity': drift_severity
    }

def decide_action(drift_report: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    decisions = {}
    for col_name, data_type in drift_report['new_columns'].items():
        if data_type =='string':
            decisions[col_name] = {'action': 'ADD_TO_SCHEMA','reason': 'New nullable string column', 'risk_level': 'LOW'}
        elif data_type.startswith('float'):
            decisions[col_name] = {'action': 'FLAG_ANOMALY','reason': 'New float column', 'risk_level': 'HIGH'}
        else:
            decisions[col_name] = {'action': 'ADD_TO_SCHEMA','reason': f'New {data_type} column', 'risk_level': 'LOW'}
    for col_name in drift_report['removed_columns']:
        decisions[col_name] = {'action': 'HALT','reason': 'Removed column', 'risk_level': 'BREAKING'}
    for col_name, (old_type, new_type) in drift_report['type_changes'].items():
        if old_type!= new_type.split('<')[0]:
            decisions[col_name] = {'action': 'FLAG_ANOMALY','reason': f'Type change from {old_type} to {new_type}', 'risk_level': 'HIGH'}
        else:
            decisions[col_name] = {'action': 'ADD_TO_SCHEMA','reason': f'Type widened from {old_type} to {new_type}', 'risk_level': 'LOW'}
    return decisions

def apply_schema_evolution(spark_df, decisions: Dict[str, Dict[str, str]], updated_schema: Dict[str, str]) -> Tuple[Any, List[str]]:
    migration_notes = []
    for col_name, action_info in decisions.items():
        if action_info['action'] == 'DROP_SILENTLY':
            spark_df = spark_df.drop(col_name)
        elif action_info['action'] == 'FLAG_ANOMALY':
            spark_df = spark_df.withColumn(f'{col_name}_anomaly', F.when(F.col(col_name).isNull(), True).otherwise(False))
            migration_notes.append(f'Column {col_name} flagged for anomaly: {action_info["reason"]}')
    return spark_df, migration_notes

def handle_drift(expected_schema: Dict[str, str], actual_schema: Dict[str, str], spark_df=None) -> Dict[str, Any]:
    drift_report = detect_schema_drift(expected_schema, actual_schema)
    decisions = decide_action(drift_report)
    print(f"Drift detected: {drift_report['drift_severity']}")
    if spark_df is not None:
        evolved_df, migration_notes = apply_schema_evolution(spark_df, decisions, actual_schema)
        return {'drift_report': drift_report, 'decisions': decisions,'migration_notes': migration_notes, 'evolved_df': evolved_df}
    return {'drift_report': drift_report, 'decisions': decisions}
