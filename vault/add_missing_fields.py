#!/usr/bin/env python3
"""
Script to add missing fields from create_ocsf_tables.py to OCSF YAML templates.
This script reads the table definitions and adds any missing fields to the templates.
"""

import re
import yaml
from pathlib import Path
from typing import Set, List, Tuple

def extract_table_fields(py_file: Path, table_name: str) -> Set[str]:
    """Extract field names from a CREATE TABLE statement in the Python file."""
    with open(py_file, 'r') as f:
        content = f.read()
    
    patterns = [
        rf'\.{table_name}\s*\((.*?)\)\s*USING',
        rf'`{table_name}`\s*\((.*?)\)\s*USING',
    ]
    
    match = None
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            break
    
    if not match:
        return set()
    
    table_def = match.group(1)
    fields = set()
    lines = table_def.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith("COMMENT '") and not re.match(r'^\w+\s', line):
            continue
        
        if line.startswith('dsl_id'):
            continue
        
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
                        base_field = field_name.split('.')[0]
                        fields.add(field_name)
                        fields.add(base_field)
    
    return fields

def normalize_field_name(field: str) -> str:
    """Normalize field names for comparison."""
    return field.lower().replace('_', '')

def get_missing_fields(table_fields: Set[str], yaml_fields: Set[str]) -> Set[str]:
    """Get fields that are in table but not in YAML."""
    table_normalized = {normalize_field_name(f): f for f in table_fields}
    yaml_normalized = {normalize_field_name(f): f for f in yaml_fields}
    
    missing = set()
    for norm_field, orig_field in table_normalized.items():
        found = False
        for yaml_norm, yaml_orig in yaml_normalized.items():
            if norm_field == yaml_norm or yaml_orig.startswith(orig_field + '.'):
                found = True
                break
        if not found:
            missing.add(orig_field)
    
    return missing

def add_fields_to_yaml(yaml_file: Path, missing_fields: Set[str]):
    """Add missing fields to the YAML template, preserving structure."""
    with open(yaml_file, 'r') as f:
        lines = f.readlines()
    
    # Find metadata section and raw_data section
    metadata_idx = -1
    raw_data_idx = -1
    
    for i, line in enumerate(lines):
        if '# Metadata (OCSF Standard Fields)' in line:
            metadata_idx = i
        if 'name: raw_data' in line and '- name: raw_data' in line:
            raw_data_idx = i
            break
    
    # Determine insertion point - before metadata section
    insert_idx = metadata_idx if metadata_idx > 0 else (raw_data_idx if raw_data_idx > 0 else len(lines) - 1)
    
    # Create field entries to insert
    new_field_lines = []
    for field_name in sorted(missing_fields):
        # Create appropriate field entry
        if field_name in ['unmapped', 'enrichments', 'observables']:
            new_field_lines.append(f"      - name: {field_name}")
            new_field_lines.append(f"        expr: # TODO: Map to your source field (VARIANT/ARRAY)")
        elif field_name == 'timezone_offset':
            new_field_lines.append(f"      - name: {field_name}")
            new_field_lines.append(f"        expr: # TODO: Map to your source field (timezone offset in minutes)")
        elif field_name in ['severity', 'status', 'disposition', 'action', 'activity', 'message']:
            new_field_lines.append(f"      - name: {field_name}")
            new_field_lines.append(f"        expr: # TODO: Map to your source field")
        elif field_name.endswith('_id'):
            new_field_lines.append(f"      - name: {field_name}")
            new_field_lines.append(f"        expr: # TODO: Map to your source field")
        else:
            new_field_lines.append(f"      - name: {field_name}")
            new_field_lines.append(f"        expr: # TODO: Map to your source field")
        new_field_lines.append("")
    
    # Remove trailing empty line
    if new_field_lines and new_field_lines[-1] == "":
        new_field_lines.pop()
    
    # Insert the new fields
    if new_field_lines:
        # Convert to list of lines with newlines
        new_field_lines_with_newlines = [line + '\n' for line in new_field_lines]
        lines[insert_idx:insert_idx] = new_field_lines_with_newlines
    
    # Write back
    with open(yaml_file, 'w') as f:
        f.writelines(lines)

def main():
    base_dir = Path(__file__).parent.parent
    py_file = base_dir / 'notebooks' / 'create_ocsf_tables.py'
    templates_dir = base_dir / 'ocsf_templates'
    
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
    
    total_added = 0
    
    for table_name, yaml_path in table_to_yaml.items():
        yaml_file = templates_dir / yaml_path
        
        if not yaml_file.exists():
            print(f"⚠️  YAML file not found: {yaml_file}")
            continue
        
        print(f"\nProcessing: {table_name}")
        
        # Extract fields
        table_fields = extract_table_fields(py_file, table_name)
        yaml_fields = extract_yaml_fields(yaml_file)
        
        # Get missing fields
        missing = get_missing_fields(table_fields, yaml_fields)
        
        if missing:
            print(f"  Adding {len(missing)} missing fields: {', '.join(sorted(missing))}")
            add_fields_to_yaml(yaml_file, missing)
            total_added += len(missing)
            print(f"  ✅ Added {len(missing)} fields to {table_name}")
        else:
            print(f"  ✅ No missing fields")
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: Added {total_added} fields across all templates")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
