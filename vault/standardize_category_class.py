#!/usr/bin/env python3
"""
Script to standardize the category & class section in all OCSF YAML templates.
Based on the OCSF schema at https://schema.ocsf.io/

Standard format (following authorize_session.yaml example):
  - name: category_name
    literal: <Category Name>
  - name: category_uid
    expr: CAST(<uid> AS INT)
  - name: class_name
    literal: <Class Name>
  - name: class_uid
    expr: CAST(<uid> AS INT)
"""

import re
import yaml
from pathlib import Path
from typing import Dict, Tuple

# OCSF Schema mapping from https://schema.ocsf.io/
# Format: table_name: (category_name, category_uid, class_name, class_uid)
OCSF_SCHEMA = {
    # System Activity [1]
    'file_activity': ('System Activity', 1, 'File System Activity', 1001),
    'kernel_extension_activity': ('System Activity', 1, 'Kernel Extension Activity', 1003),
    'scheduled_job_activity': ('System Activity', 1, 'Scheduled Job Activity', 1006),
    'process_activity': ('System Activity', 1, 'Process Activity', 1007),
    'script_activity': ('System Activity', 1, 'Script Activity', 1008),
    
    # Findings [2]
    'vulnerability_finding': ('Findings', 2, 'Vulnerability Finding', 2002),  # Note: 2002 per OCSF schema
    'data_security_finding': ('Findings', 2, 'Data Security Finding', 2006),  # Note: 2006 per OCSF schema
    
    # Identity & Access Management [3]
    'account_change': ('Identity & Access Management', 3, 'Account Change', 3001),
    'authentication': ('Identity & Access Management', 3, 'Authentication', 3002),
    'authorize_session': ('Identity & Access Management', 3, 'Authorize Session', 3003),
    'entity_management': ('Identity & Access Management', 3, 'Entity Management', 3004),
    'user_access': ('Identity & Access Management', 3, 'User Access Management', 3005),
    'group_management': ('Identity & Access Management', 3, 'Group Management', 3006),
    
    # Network Activity [4]
    'network_activity': ('Network Activity', 4, 'Network Activity', 4001),
    'http_activity': ('Network Activity', 4, 'HTTP Activity', 4002),
    'dns_activity': ('Network Activity', 4, 'DNS Activity', 4003),
    'dhcp_activity': ('Network Activity', 4, 'DHCP Activity', 4004),
    'ssh_activity': ('Network Activity', 4, 'SSH Activity', 4007),
    'email_activity': ('Network Activity', 4, 'Email Activity', 4009),
    
    # Application Activity [6]
    'api_activity': ('Application Activity', 6, 'API Activity', 6003),
    'datastore_activity': ('Application Activity', 6, 'Datastore Activity', 6005),  # Note: Should be 6005, not 4007
}

def standardize_template(yaml_file: Path, category_name: str, category_uid: int, class_name: str, class_uid: int):
    """Standardize the category & class section in a YAML template."""
    with open(yaml_file, 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Find all lines with category/class fields
    category_lines = []
    for i, line in enumerate(lines):
        if ('category_uid' in line or 'category_name' in line or 
            'class_uid' in line or 'class_name' in line) and '- name:' in line:
            category_lines.append(i)
    
    if not category_lines:
        print(f"  ⚠️  Could not find category/class section in {yaml_file.name}")
        return False
    
    # Find the range - from first category/class line to after the last one
    start_idx = min(category_lines)
    end_idx = max(category_lines) + 1
    
    # Look for the end - find the next field that's not category/class related
    for i in range(end_idx, len(lines)):
        stripped = lines[i].strip()
        if stripped and stripped.startswith('- name:') and 'category' not in stripped and 'class' not in stripped:
            end_idx = i
            break
    
    # Check for comment before
    comment_before = False
    if start_idx > 0 and lines[start_idx - 1].strip().startswith('#'):
        comment_before = True
        start_idx -= 1
    
    # Create the standardized section
    new_section = []
    new_section.append("      # Category & Class")
    new_section.append(f"      - name: category_name")
    new_section.append(f"        literal: {category_name}")
    new_section.append(f"      - name: category_uid")
    new_section.append(f"        expr: CAST({category_uid} AS INT)")
    new_section.append(f"      - name: class_name")
    new_section.append(f"        literal: {class_name}")
    new_section.append(f"      - name: class_uid")
    new_section.append(f"        expr: CAST({class_uid} AS INT)")
    new_section.append("      ")  # Empty line after
    
    # Replace the section
    new_lines = lines[:start_idx] + new_section + lines[end_idx:]
    
    # Write back
    with open(yaml_file, 'w') as f:
        f.write('\n'.join(new_lines))
        if not content.endswith('\n'):
            f.write('\n')
    
    return True

def main():
    base_dir = Path(__file__).parent.parent
    templates_dir = base_dir / 'ocsf_templates'
    
    # Map table names to YAML file paths
    table_to_yaml = {
        'account_change': 'identity_access_management/account_change.yaml',
        'api_activity': 'application_activity/api_activity.yaml',
        'authentication': 'identity_access_management/authentication.yaml',
        'authorize_session': 'identity_access_management/authorize_session.yaml',
        'data_security_finding': 'findings/data_security_finding.yaml',
        'datastore_activity': 'network_activity/datastore_activity.yaml',  # Note: Should move to application_activity?
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
    
    updated_count = 0
    
    for table_name, yaml_path in table_to_yaml.items():
        if table_name not in OCSF_SCHEMA:
            print(f"⚠️  No schema definition for {table_name}")
            continue
        
        yaml_file = templates_dir / yaml_path
        
        if not yaml_file.exists():
            print(f"⚠️  YAML file not found: {yaml_file}")
            continue
        
        category_name, category_uid, class_name, class_uid = OCSF_SCHEMA[table_name]
        
        print(f"\nProcessing: {table_name}")
        print(f"  Category: {category_name} ({category_uid})")
        print(f"  Class: {class_name} ({class_uid})")
        
        if standardize_template(yaml_file, category_name, category_uid, class_name, class_uid):
            updated_count += 1
            print(f"  ✅ Standardized {yaml_file.name}")
        else:
            print(f"  ❌ Failed to standardize {yaml_file.name}")
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: Standardized {updated_count} templates")
    print(f"{'='*60}")
    print("\nNote: Based on OCSF schema at https://schema.ocsf.io/")
    print("Standard format:")
    print("  - name: category_name")
    print("    literal: <Category Name>")
    print("  - name: category_uid")
    print("    expr: CAST(<uid> AS INT)")
    print("  - name: class_name")
    print("    literal: <Class Name>")
    print("  - name: class_uid")
    print("    expr: CAST(<uid> AS INT)")

if __name__ == '__main__':
    main()

