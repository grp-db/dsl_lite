#!/usr/bin/env python3
"""
Script to compare OCSF table schemas in create_ocsf_tables.py with YAML templates.
Checks that all fields from table definitions are present in the corresponding YAML templates.
"""

import re
import yaml
from pathlib import Path
from typing import Set, Dict, List, Tuple

def extract_table_fields(py_file: Path, table_name: str) -> Set[str]:
    """Extract field names from a CREATE TABLE statement in the Python file."""
    with open(py_file, 'r') as f:
        content = f.read()
    
    # Find the CREATE TABLE statement for this table
    # The pattern is: CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.table_name (
    # The table name appears without backticks: .table_name
    patterns = [
        rf'\.{table_name}\s*\((.*?)\)\s*USING',  # .table_name (
        rf'`{table_name}`\s*\((.*?)\)\s*USING',  # `table_name` (
    ]
    
    match = None
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            break
    
    if not match:
        print(f"  ⚠️  Could not find table definition for {table_name}")
        return set()
    
    table_def = match.group(1)
    
    # Extract field names - each field is on a line starting with field name
    fields = set()
    lines = table_def.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip COMMENT lines that are standalone
        if line.startswith("COMMENT '") and not re.match(r'^\w+\s', line):
            continue
        
        # Skip dsl_id as it's auto-generated
        if line.startswith('dsl_id'):
            continue
        
        # Extract field name - it's the first word before a space
        # Handle cases like: "action STRING" or "actor STRUCT<...>"
        field_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s', line)
        if field_match:
            field_name = field_match.group(1)
            fields.add(field_name)
    
    return fields

def extract_yaml_fields(yaml_file: Path) -> Set[str]:
    """Extract field names from a YAML template file."""
    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f)
    
    fields = set()
    
    if 'gold' in data and isinstance(data['gold'], list):
        for gold_item in data['gold']:
            if 'fields' in gold_item and isinstance(gold_item['fields'], list):
                for field in gold_item['fields']:
                    if 'name' in field:
                        field_name = field['name']
                        # Remove nested field paths (e.g., "metadata.version" -> "metadata")
                        # We'll handle nested fields separately
                        base_field = field_name.split('.')[0]
                        fields.add(field_name)  # Keep full path for nested fields
                        fields.add(base_field)  # Also add base field
    
    return fields

def normalize_field_name(field: str) -> str:
    """Normalize field names for comparison."""
    # Remove underscores, convert to lowercase for comparison
    return field.lower().replace('_', '')

def compare_fields(table_fields: Set[str], yaml_fields: Set[str]) -> Tuple[Set[str], Set[str]]:
    """Compare table fields with YAML fields and return missing fields."""
    # Normalize for comparison
    table_normalized = {normalize_field_name(f): f for f in table_fields}
    yaml_normalized = {normalize_field_name(f): f for f in yaml_fields}
    
    # Find missing fields
    missing = set()
    for norm_field, orig_field in table_normalized.items():
        # Check if field exists in YAML (exact match or nested)
        found = False
        for yaml_norm, yaml_orig in yaml_normalized.items():
            if norm_field == yaml_norm or yaml_orig.startswith(orig_field + '.'):
                found = True
                break
        if not found:
            missing.add(orig_field)
    
    return missing, set()

def main():
    base_dir = Path(__file__).parent.parent  # Go up from vault/ to project root
    py_file = base_dir / 'notebooks' / 'create_ocsf_tables.py'
    templates_dir = base_dir / 'ocsf_templates'
    
    # Map table names to YAML file paths
    table_to_yaml = {
        'account_change': 'identity_access_management/account_change.yaml',
        'api_activity': 'application_activity/api_activity.yaml',
        'authentication': 'identity_access_management/authentication.yaml',
        'authorize_session': 'identity_access_management/authorize_session.yaml',
        'data_security_finding': 'findings/data_security_finding.yaml',
        'datastore_activity': 'network_activity/datastore_activity.yaml',
        'dhcp_activity': 'network_activity/dhcp_activity.yaml',
        'dns_activity': 'network_activity/dns_activity.yaml',
        'email_activity': 'network_activity/email_activity.yaml',
        'entity_management': 'identity_access_management/entity_management.yaml',
        'file_activity': 'system_activity/file_activity.yaml',
        'group_management': 'identity_access_management/group_management.yaml',
        'http_activity': 'network_activity/http_activity.yaml',
        'kernel_extension_activity': 'system_activity/kernel_extension_activity.yaml',
        'network_activity': 'network_activity/network_activity.yaml',
        'process_activity': 'system_activity/process_activity.yaml',
        'scheduled_job_activity': 'system_activity/scheduled_job_activity.yaml',
        'script_activity': 'system_activity/script_activity.yaml',
        'ssh_activity': 'network_activity/ssh_activity.yaml',
        'user_access': 'identity_access_management/user_access.yaml',
        'vulnerability_finding': 'findings/vulnerability_finding.yaml',
    }
    
    all_missing = {}
    all_results = []
    
    for table_name, yaml_path in table_to_yaml.items():
        yaml_file = templates_dir / yaml_path
        
        if not yaml_file.exists():
            print(f"⚠️  YAML file not found: {yaml_file}")
            continue
        
        print(f"\n{'='*60}")
        print(f"Checking: {table_name}")
        print(f"{'='*60}")
        
        # Extract fields
        table_fields = extract_table_fields(py_file, table_name)
        yaml_fields = extract_yaml_fields(yaml_file)
        
        print(f"Table fields: {len(table_fields)}")
        print(f"YAML fields: {len(yaml_fields)}")
        
        # Compare
        missing, extra = compare_fields(table_fields, yaml_fields)
        
        if missing:
            all_missing[table_name] = missing
            print(f"\n❌ Missing fields ({len(missing)}):")
            for field in sorted(missing):
                print(f"  - {field}")
        else:
            print(f"\n✅ All table fields are present in YAML template")
        
        all_results.append({
            'table': table_name,
            'table_fields_count': len(table_fields),
            'yaml_fields_count': len(yaml_fields),
            'missing_count': len(missing),
            'missing_fields': sorted(missing) if missing else []
        })
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    total_missing = sum(len(m) for m in all_missing.values())
    tables_with_missing = len(all_missing)
    
    print(f"Tables checked: {len(table_to_yaml)}")
    print(f"Tables with missing fields: {tables_with_missing}")
    print(f"Total missing fields: {total_missing}")
    
    if all_missing:
        print(f"\nTables needing updates:")
        for table, fields in sorted(all_missing.items()):
            print(f"  - {table}: {len(fields)} missing fields")
    
    return all_results

if __name__ == '__main__':
    main()

