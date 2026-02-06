#!/usr/bin/env python3
"""
Script to:
1. Fix duplicate metadata sections in OCSF templates
2. Update templates to include all columns from create_ocsf_tables.py DDL
"""

import re
from pathlib import Path
from typing import Dict, List, Set

# Standard metadata fields (in correct order)
STANDARD_METADATA = """      # Metadata (OCSF Standard Fields)
      - name: metadata.version
        literal: "1.7.0"  # OCSF schema version
      - name: metadata.product.name
        literal: # Product name (e.g., "Zeek Conn", "Cisco IOS")
      - name: metadata.product.vendor_name
        literal: # Vendor name (e.g., "Zeek", "Cisco")
      - name: metadata.log_provider
        literal: # Log provider/source (e.g., "zeek", "cisco", "cloudflare")
      - name: metadata.log_name
        literal: # Log name/sourcetype (e.g., "conn", "ios", "gateway_dns")
      - name: metadata.log_format
        literal: # Log format (e.g., "JSON", "syslog", "CSV")
      - name: metadata.log_version
        literal: # Schema version format: "source@sourcetype:version@1.0" (e.g., "zeek@conn:version@1.0")
      - name: metadata.processed_time
        expr: CURRENT_TIMESTAMP()  # When processed by pipeline
      - name: metadata.logged_time
        from: time  # When the event was logged (REQUIRED: map to your time field)"""

def extract_columns_from_ddl(ddl_file: Path) -> Dict[str, List[str]]:
    """Extract column names from CREATE TABLE statements in DDL file."""
    with open(ddl_file, 'r') as f:
        content = f.read()
    
    tables = {}
    # Find all CREATE TABLE statements
    pattern = r'CREATE OR REPLACE TABLE.*?\.(\w+)\s*\((.*?)\)USING delta'
    
    for match in re.finditer(pattern, content, re.DOTALL):
        table_name = match.group(1)
        columns_section = match.group(2)
        
        # Extract column names (first word after dsl_id or comma)
        columns = ['dsl_id']  # Always first
        # Find all column definitions
        col_pattern = r'(\w+(?:\.\w+)*)\s+(?:STRING|INT|BIGINT|BOOLEAN|TIMESTAMP|VARIANT|STRUCT|ARRAY)'
        for col_match in re.finditer(col_pattern, columns_section):
            col_name = col_match.group(1)
            if col_name != 'dsl_id' and col_name not in columns:
                columns.append(col_name)
        
        tables[table_name] = columns
    
    return tables

def fix_metadata_duplicates(content: str) -> str:
    """Remove duplicate metadata sections and standardize."""
    lines = content.split('\n')
    new_lines = []
    i = 0
    metadata_found = False
    
    while i < len(lines):
        line = lines[i]
        
        # Find start of metadata section
        if '# Metadata' in line and not metadata_found:
            # Add standard metadata
            for meta_line in STANDARD_METADATA.split('\n'):
                new_lines.append(meta_line)
            metadata_found = True
            
            # Skip all old metadata lines until we hit a non-metadata field
            i += 1
            while i < len(lines):
                if lines[i].strip().startswith('- name: metadata.'):
                    i += 1
                    # Skip continuation lines
                    while i < len(lines) and (lines[i].strip().startswith('expr:') or 
                                             lines[i].strip().startswith('literal:') or 
                                             lines[i].strip().startswith('from:') or
                                             (lines[i].strip().startswith('#') and 'OCSF' not in lines[i])):
                        i += 1
                    continue
                elif lines[i].strip().startswith('#'):
                    if 'Metadata' in lines[i] and 'OCSF' not in lines[i]:
                        i += 1
                        continue
                elif not lines[i].strip():
                    i += 1
                    continue
                else:
                    # Hit a non-metadata field, stop skipping
                    break
            # Add empty line after metadata
            new_lines.append('')
            continue
        
        new_lines.append(line)
        i += 1
    
    return '\n'.join(new_lines)

def main():
    base_dir = Path(__file__).parent.parent  # Go up from vault/ to project root
    templates_dir = base_dir / "ocsf_templates"
    ddl_file = base_dir / "notebooks" / "create_ocsf_tables.py"
    
    # Extract columns from DDL (this is a simplified version - full implementation would parse more carefully)
    print("Note: Column extraction from DDL is complex. For now, fixing metadata duplicates...")
    
    # Fix metadata in all templates
    template_files = list(templates_dir.rglob("*.yaml"))
    for file_path in template_files:
        if file_path.name == "README.md":
            continue
        
        print(f"Processing: {file_path}")
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Fix metadata duplicates
        content = fix_metadata_duplicates(content)
        
        with open(file_path, 'w') as f:
            f.write(content)
    
    print(f"\nFixed metadata in {len(template_files)} template files")
    print("\nNote: To fully update templates with all DDL columns, this requires")
    print("      more sophisticated parsing of the DDL file structure.")

if __name__ == "__main__":
    main()


