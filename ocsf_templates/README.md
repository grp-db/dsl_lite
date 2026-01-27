# OCSF Gold Mapping Templates

This directory contains starter templates for mapping your data to OCSF (Open Cybersecurity Schema Framework) gold tables.

## Available Templates

All 21 OCSF gold table templates are organized by category:

### Network Activity (Category 4) - `network_activity/`
- **network_activity.yaml** - Network connections, flows, and traffic (Class UID: 4001)
- **dns_activity.yaml** - DNS queries and responses (Class UID: 4003)
- **http_activity.yaml** - HTTP/HTTPS requests and responses (Class UID: 4002)
- **dhcp_activity.yaml** - DHCP address assignments (Class UID: 4004)
- **ssh_activity.yaml** - SSH connections and file transfers (Class UID: 4007)
- **datastore_activity.yaml** - Database operations (Class UID: 4007)
- **email_activity.yaml** - Email sending/receiving (Class UID: 4009)

### Identity & Access Management (Category 3) - `identity_access_management/`
- **authentication.yaml** - User login/logout events (Class UID: 3002)
- **account_change.yaml** - Account modifications (Class UID: 3001)
- **authorize_session.yaml** - Authorization decisions (Class UID: 3003)
- **entity_management.yaml** - Entity lifecycle (Class UID: 3004)
- **user_access.yaml** - Resource access events (Class UID: 3005)
- **group_management.yaml** - Group membership changes (Class UID: 3006)

### System Activity (Category 1) - `system_activity/`
- **file_activity.yaml** - File system operations (Class UID: 1001)
- **kernel_extension_activity.yaml** - Kernel module loading (Class UID: 1003)
- **scheduled_job_activity.yaml** - Scheduled tasks (Class UID: 1006)
- **process_activity.yaml** - Process lifecycle events (Class UID: 1007)
- **script_activity.yaml** - Script execution (Class UID: 1008)

### Findings (Category 2) - `findings/`
- **vulnerability_finding.yaml** - Vulnerability scan results (Class UID: 2001)
- **data_security_finding.yaml** - Data security issues (Class UID: 2003)

### Application Activity (Category 6) - `application_activity/`
- **api_activity.yaml** - API calls and responses (Class UID: 6003)

## Usage

### 1. Copy a Template

```bash
cp ocsf_templates/network_activity/network_activity.yaml pipelines/my_source/network_activity/preset.yaml
```

### 2. Update the Configuration

Edit the copied file and:
1. Change `<YOUR_SILVER_TABLE_NAME>` to your actual silver table name
2. Add a `filter` condition if needed to select relevant events
3. Fill in the field mappings using `expr`, `from`, or `literal`

### 3. Field Mapping Options

#### Option 1: Use `from` for direct column mapping
```yaml
- name: time
  from: event_timestamp
```

#### Option 2: Use `expr` for expressions
```yaml
- name: activity_id
  expr: |
    CAST(
      CASE 
        WHEN action = 'connect' THEN '1'
        WHEN action = 'disconnect' THEN '2'
        ELSE '0'
      END
    AS INT)
```

#### Option 3: Use `literal` for constant values
```yaml
- name: category_name
  literal: Network Activity
```

#### Option 4: Use `from` with nested fields
```yaml
- name: src_endpoint.ip
  from: source_ip
```

### 4. Complete Example

See `pipelines/zeek/conn/preset.yaml` for a fully implemented example of network_activity mapping from Zeek connection logs.

## Required vs Optional Fields

### Always Required (OCSF Core)
- `activity_id` - Numeric activity identifier
- `activity_name` - Human-readable activity name
- `category_uid` - OCSF category (e.g., 4 for Network Activity)
- `category_name` - Category name
- `class_uid` - OCSF class (e.g., 4001 for Network Activity)
- `class_name` - Class name
- `time` - Event timestamp
- `type_uid` - Calculated as `class_uid * 100 + activity_id`
- `type_name` - Type description

### Recommended Fields
- `severity_id` - Event severity (0-6)
- `metadata.product.name` - Source product name
- `metadata.product.vendor_name` - Vendor name
- `metadata.logged_time` - Original log time
- `metadata.processed_time` - Processing timestamp
- `raw_data` - Original event data (for audit/debugging)

### Optional Fields
Comment out or remove any fields you don't have data for.

## OCSF Activity IDs

### Network Activity (4001)
- 1 = Open (connection established)
- 2 = Close (connection closed)
- 3 = Send (data sent)
- 4 = Receive (data received)
- 5 = Bind (listening)
- 6 = Traffic (general network traffic)

### DNS Activity (4003)
- 1 = Query (DNS request)
- 2 = Response (DNS answer)

### Authentication (3002)
- 1 = Logon
- 2 = Logoff
- 3 = Authentication Ticket

### File Activity (1001)
- 1 = Create
- 2 = Read
- 3 = Update
- 4 = Delete
- 5 = Rename
- 12 = Mount
- 13 = Unmount
- 14 = Open

### Process Activity (1007)
- 1 = Launch
- 2 = Terminate
- 3 = Open
- 4 = Inject
- 5 = Set User ID

## Tips

1. **Start Simple**: Begin with required fields only, add optional fields as needed
2. **Test Incrementally**: Test your mapping with a small dataset first
3. **Use Filters**: Add filter conditions to select only relevant events
4. **Preserve Raw Data**: Always include `raw_data` field for debugging
5. **Document Mappings**: Add comments explaining complex expressions

## Field Naming Conventions

OCSF uses dot notation for nested fields:
- `src_endpoint.ip` - Source endpoint IP address
- `metadata.product.name` - Product name in metadata
- `process.file.hashes` - Hashes of process file

## Common Patterns

### Mapping IP addresses
```yaml
- name: src_endpoint.ip
  expr: coalesce(source_ipv4, source_ipv6)
- name: dst_endpoint.ip
  expr: coalesce(dest_ipv4, dest_ipv6)
```

### Protocol number mapping
```yaml
- name: connection_info.protocol_num
  expr: |
    CAST((
      CASE 
        WHEN LOWER(protocol) = 'icmp' THEN 1
        WHEN LOWER(protocol) = 'tcp' THEN 6
        WHEN LOWER(protocol) = 'udp' THEN 17
        ELSE NULL 
      END)
    AS INT)
```

### Direction mapping
```yaml
- name: connection_info.direction_id
  expr: |
    CASE
      WHEN src_is_internal AND dst_is_internal THEN 3  -- Lateral
      WHEN src_is_internal AND NOT dst_is_internal THEN 2  -- Outbound
      WHEN NOT src_is_internal AND dst_is_internal THEN 1  -- Inbound
      ELSE 4  -- Unknown
    END
```

## Resources

- [OCSF Schema Browser](https://schema.ocsf.io/)
- [OCSF GitHub](https://github.com/ocsf)
- Example: `pipelines/zeek/conn/preset.yaml`
- Schema Definitions: `create_ocsf_tables.py`

## Need Help?

1. Check the complete example in `pipelines/zeek/conn/preset.yaml`
2. Review the field definitions in `create_ocsf_tables.py`
3. Consult the OCSF schema documentation at https://schema.ocsf.io/
