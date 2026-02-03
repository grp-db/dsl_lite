# Databricks notebook source
"""
DSL Lite - OCSF Table Creation

OCSF (Open Cybersecurity Schema Framework) Gold Table Definitions
Reference: https://schema.ocsf.io/

This notebook creates OCSF-compliant tables for the gold layer. OCSF organizes
event classes into categories aligned with specific security domains:

Categories:
- Category 1: System Activity (process, file, kernel events)
- Category 2: Findings (security, vulnerability, compliance findings)
- Category 3: Identity & Access Management (authentication, authorization)
- Category 4: Network Activity (network, DNS, HTTP, email)
- Category 5: Discovery (inventory, queries)
- Category 6: Application Activity (API, web resources, datastores)

Common OCSF Field Patterns:
- *_id fields: Numeric identifiers (e.g., activity_id, severity_id)
- *_name fields: Human-readable names (e.g., activity_name, class_name)
- *_uid fields: Unique identifiers (e.g., type_uid = class_uid * 100 + activity_id)
- time: Event occurrence timestamp (required)
- metadata: Event metadata (product, version, timestamps)
- observables: Extracted indicators (IPs, domains, hashes)
- raw_data: Original event data (VARIANT for any format)
- unmapped: Vendor-specific fields not in OCSF schema
"""

catalog_name = 'dsl_lite'
gold_database = 'ocsf'
bronze_database = 'bronze' # or name of vendor oem (i.e. cisco)
silver_database = 'silver' # or name of vendor oem (i.e. cisco)

# COMMAND ----------

if catalog_name != "hive_metastore":
    spark.sql(f"CREATE CATALOG if not EXISTS `{catalog_name}`")

spark.sql(f"CREATE DATABASE if not EXISTS `{catalog_name}`.`{gold_database}`")
spark.sql(f"CREATE DATABASE if not EXISTS `{catalog_name}`.`{bronze_database}`")
spark.sql(f"CREATE DATABASE if not EXISTS `{catalog_name}`.`{silver_database}`")

# COMMAND ----------

# Account Change (Class UID: 3001, Category: Identity & Access Management)
# Tracks user account lifecycle events (create, modify, delete, lock, unlock, password changes)
# Commonly used for: Active Directory logs, IAM account management, user provisioning/deprovisioning
# Reference: https://schema.ocsf.io/1.3.0/classes/account_change
spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.account_change (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING COMMENT 'The action taken on the account change (e.g., Allowed, Denied)',
  action_id INT COMMENT 'The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other',
  activity STRING COMMENT 'The account activity name (e.g., Create, Modify, Delete, Lock). Normalized value based on activity_id.',
  activity_id INT COMMENT 'The account activity ID: 0=Unknown, 1=Create (new account), 2=Enable (activate account), 3=Password Change, 4=Password Reset, 5=Disable (deactivate account), 6=Delete, 7=Attach Policy, 8=Detach Policy, 9=Lock, 10=MFA Enable, 11=MFA Disable, 99=Other',
  activity_name STRING COMMENT 'The account activity name (e.g., Create, Delete, Password Change)',
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>> COMMENT 'The actor (admin or service) that performed the account change',
  api STRUCT<operation: STRING, request: STRUCT<data: VARIANT, uid: STRING>, response: STRUCT<code: INT, data: VARIANT, error: STRING, message: STRING>> COMMENT 'API details for programmatic account changes (e.g., AWS IAM API, Azure AD Graph API)',
  category_name STRING COMMENT 'The OCSF category name: Identity & Access Management',
  category_uid INT COMMENT 'The OCSF category unique identifier: 3 for Identity & Access Management',
  class_name STRING COMMENT 'The OCSF class name: Account Change',
  class_uid INT COMMENT 'The OCSF class unique identifier: 3001 for Account Change',
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING> COMMENT 'Cloud environment information for cloud IAM account changes (AWS IAM, Azure AD, GCP IAM)',
  disposition STRING COMMENT 'The disposition name (e.g., Allowed, Blocked). Indicates if account change was successful or prevented.',
  disposition_id INT COMMENT 'The disposition ID: 0=Unknown, 1=Allowed, 2=Blocked, 99=Other',
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>> COMMENT 'Additional enrichment data from risk scoring or threat intelligence',
  message STRING COMMENT 'Human-readable description of the account change event',
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING> COMMENT 'Event metadata including product info, timestamps, and unique identifiers',
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>> COMMENT 'Observable artifacts: account names, admin usernames, source IPs - critical for insider threat detection',
  policies ARRAY<STRUCT<is_applied: BOOLEAN, name: STRING, uid: STRING, version: STRING>> COMMENT 'IAM policies attached or detached from the account',
  raw_data VARIANT COMMENT 'The original raw account change log in its native format',
  severity STRING COMMENT 'The event severity name (e.g., Informational, Low, Medium, High, Critical)',
  severity_id INT COMMENT 'The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other',
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The source endpoint (admin workstation or API caller) that initiated the account change',
  status STRING COMMENT 'The event status name (e.g., Success, Failure)',
  status_code STRING COMMENT 'The vendor-specific status or error code',
  status_detail STRING COMMENT 'Additional details about the account change status or error',
  status_id INT COMMENT 'The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other',
  time TIMESTAMP COMMENT 'The account change event time (required field)',
  timezone_offset INT COMMENT 'The timezone offset in minutes from UTC',
  type_name STRING COMMENT 'The event type name, formatted as "Account Change: <activity_name>"',
  type_uid BIGINT COMMENT 'The event type unique identifier, calculated as class_uid * 100 + activity_id',
  unmapped VARIANT COMMENT 'Vendor-specific account management fields that do not map to OCSF schema attributes',
  user STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING> COMMENT 'The user account before the change (previous state)',
  user_result STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING> COMMENT 'The user account after the change (new state) - use this to track what changed')
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.api_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity_id INT,
  activity_name STRING,
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>,
  api STRUCT<operation: STRING, request: STRUCT<data: VARIANT, uid: STRING>, response: STRUCT<code: INT, data: VARIANT, error: STRING, message: STRING>>,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING>,
  disposition STRING,
  disposition_id INT,
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  http_request STRUCT<args: STRING, body_length: INT, http_headers: ARRAY<STRUCT<name: STRING, value: STRING>>, http_method: STRING, length: INT, referrer: STRING, url: STRING, user_agent: STRING, version: STRING>,
  http_response STRUCT<body_length: INT, code: INT, content_type: STRING, http_headers: ARRAY<STRUCT<name: STRING, value: STRING>>, latency: INT, length: INT, message: STRING, status: STRING>,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  raw_data VARIANT,
  resources ARRAY<STRUCT<hostname: STRING, ip: STRING, name: STRING, uid: STRING>>,
  severity STRING,
  severity_id INT,
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  start_time TIMESTAMP,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  time TIMESTAMP,
  timezone_offset INT,
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

# Authentication (Class UID: 3002, Category: Identity & Access Management)
# Tracks user authentication events (logon, logoff, authentication failures)
# Reference: https://schema.ocsf.io/1.3.0/classes/authentication
spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.authentication (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING COMMENT 'The action taken by the system (e.g., Allowed, Denied). See action_id for numeric representation.',
  action_id INT COMMENT 'The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other',
  activity STRING COMMENT 'The authentication activity name (e.g., Logon, Logoff). Normalized value based on activity_id.',
  activity_id INT COMMENT 'The authentication activity ID: 0=Unknown, 1=Logon, 2=Logoff, 3=Authentication Ticket, 4=Service Ticket Request, 99=Other',
  activity_name STRING COMMENT 'The authentication activity name (e.g., Logon, Logoff)',
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>,
  auth_factors ARRAY<STRUCT<factor_type: STRING, factor_type_id: INT>> COMMENT 'Authentication factors used (e.g., password, MFA token, biometric)',
  auth_protocol STRING COMMENT 'The authentication protocol (e.g., NTLM, Kerberos, SAML, OAuth)',
  auth_protocol_id INT COMMENT 'The authentication protocol ID: 0=Unknown, 1=NTLM, 2=Kerberos, 3=Digest, 4=OpenID, 5=SAML, 6=OAuth, 7=SSO, 8=CHAP, 9=PAP, 10=RADIUS, 11=LDAP, 99=Other',
  category_name STRING COMMENT 'The OCSF category name: Identity & Access Management',
  category_uid INT COMMENT 'The OCSF category unique identifier: 3 for Identity & Access Management',
  class_name STRING COMMENT 'The OCSF class name: Authentication',
  class_uid INT COMMENT 'The OCSF class unique identifier: 3002 for Authentication',
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING>,
  disposition STRING COMMENT 'The event disposition name (e.g., Allowed, Blocked, Quarantined). Describes the outcome/action taken.',
  disposition_id INT COMMENT 'The disposition ID: 0=Unknown, 1=Allowed, 2=Blocked, 3=Quarantined, 4=Isolated, 5=Deleted, 6=Dropped, 7=Custom Action, 8=Approved, 9=Restored, 10=Exonerated, 99=Other',
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The destination endpoint (authentication target/server)',
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>> COMMENT 'Additional enrichment data from threat intel, GeoIP, or other sources',
  is_mfa BOOLEAN COMMENT 'Indicates whether multi-factor authentication was used',
  is_remote BOOLEAN COMMENT 'Indicates whether the authentication was from a remote location',
  logon_type STRING COMMENT 'The logon type name (e.g., Interactive, Network, Service)',
  logon_type_id INT COMMENT 'The Windows logon type ID: 0=Unknown, 2=Interactive, 3=Network, 4=Batch, 5=Service, 7=Unlock, 8=NetworkCleartext, 9=NewCredentials, 10=RemoteInteractive, 11=CachedInteractive, 99=Other',
  message STRING COMMENT 'Human-readable description of the event',
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING> COMMENT 'Event metadata including product info, timestamps, and unique identifiers',
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>> COMMENT 'Observable artifacts extracted from the event (e.g., IP addresses, usernames, domains) for threat hunting',
  raw_data VARIANT COMMENT 'The original raw event data in its native format (JSON, XML, text, etc.)',
  service STRUCT<name: STRING, uid: STRING> COMMENT 'The service or application being authenticated to',
  session STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING> COMMENT 'Session information including creation time, expiration, and session attributes',
  severity STRING COMMENT 'The event severity name (e.g., Informational, Low, Medium, High, Critical)',
  severity_id INT COMMENT 'The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other',
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The source endpoint (client/device initiating authentication)',
  status STRING COMMENT 'The event status name (e.g., Success, Failure)',
  status_code STRING COMMENT 'The vendor-specific status or error code',
  status_detail STRING COMMENT 'Additional details about the status or error',
  status_id INT COMMENT 'The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other',
  time TIMESTAMP COMMENT 'The event occurrence time (required field)',
  timezone_offset INT COMMENT 'The timezone offset in minutes from UTC',
  type_name STRING COMMENT 'The event type name, formatted as "Authentication: <activity_name>"',
  type_uid BIGINT COMMENT 'The event type unique identifier, calculated as class_uid * 100 + activity_id',
  unmapped VARIANT COMMENT 'Vendor-specific fields that do not map to OCSF schema attributes',
  user STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

# Authorize Session (Class UID: 3003, Category: Identity & Access Management)
# Tracks authorization and access control decisions (permission grants/denials, role assignments)
# Commonly used for: IAM policy evaluations, access denied events, privilege escalations, Cisco IOS authorization failures
# Reference: https://schema.ocsf.io/1.3.0/classes/authorize_session
spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.authorize_session (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING COMMENT 'The action taken on the authorization request (e.g., Allowed, Denied)',
  action_id INT COMMENT 'The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other',
  activity_id INT COMMENT 'The authorization activity ID: 0=Unknown, 1=Assign Privileges, 2=Revoke Privileges, 99=Other',
  activity_name STRING COMMENT 'The authorization activity name (e.g., Assign Privileges, Revoke Privileges)',
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>> COMMENT 'The actor (user or service) requesting authorization',
  category_name STRING COMMENT 'The OCSF category name: Identity & Access Management',
  category_uid INT COMMENT 'The OCSF category unique identifier: 3 for Identity & Access Management',
  class_name STRING COMMENT 'The OCSF class name: Authorize Session',
  class_uid INT COMMENT 'The OCSF class unique identifier: 3003 for Authorize Session',
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING> COMMENT 'Cloud environment information (AWS, Azure, GCP) for cloud IAM events',
  device STRUCT<created_time: TIMESTAMP, hostname: STRING, hw_info: STRUCT<bios_date: STRING, bios_manufacturer: STRING, bios_ver: STRING, chassis: STRING, cpu_bits: INT, cpu_cores: INT, cpu_count: INT, cpu_speed: INT, cpu_type: STRING, desktop_display: STRING, keyboard_info: STRING, ram_size: INT, serial_number: STRING>, hypervisor: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, is_compliant: BOOLEAN, is_managed: BOOLEAN, is_personal: BOOLEAN, is_trusted: BOOLEAN, last_seen_time: TIMESTAMP, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, modified_time: TIMESTAMP, name: STRING, network_interfaces: ARRAY<STRUCT<hostname: STRING, ip: STRING, mac: STRING, name: STRING, namespace: STRING, subnet_uid: STRING, type: STRING, type_id: INT, uid: STRING>>, org: STRUCT<name: STRING, ou_name: STRING, ou_uid: STRING, uid: STRING>, os: STRUCT<build: STRING, country: STRING, cpu_bits: INT, edition: STRING, lang: STRING, name: STRING, sp_name: STRING, sp_ver: INT, type: STRING, type_id: INT, version: STRING>, region: STRING, risk_level: STRING, risk_level_id: INT, subnet_uid: STRING, type: STRING, type_id: INT, uid: STRING, uid_alt: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The device from which authorization was requested (includes OS, hardware info, compliance status)',
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The destination resource/service being accessed',
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>> COMMENT 'Additional enrichment data from threat intel or risk scoring',
  http_request STRUCT<http_headers: ARRAY<STRUCT<name: STRING, value: STRING>>, http_method: STRING, referrer: STRING, url: STRUCT<hostname: STRING, path: STRING, port: INT, query_string: STRING, scheme: STRING, subdomain: STRING, text: STRING, url_string: STRING>, user_agent: STRING, version: STRING, x_forwarded_for: ARRAY<STRING>> COMMENT 'HTTP request details for web/API authorization requests',
  message STRING COMMENT 'Human-readable description of the authorization event',
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING> COMMENT 'Event metadata including product info, timestamps, and unique identifiers',
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>> COMMENT 'Observable artifacts: usernames, resource names, IP addresses - critical for access pattern analysis',
  policy STRUCT<desc: STRING, group: STRUCT<desc: STRING, name: STRING, privileges: ARRAY<STRING>, type: STRING, uid: STRING>, name: STRING, uid: STRING, version: STRING> COMMENT 'The IAM policy that was evaluated for this authorization decision',
  privileges ARRAY<STRING> COMMENT 'The specific privileges/permissions requested (e.g., read, write, execute, admin)',
  raw_data VARIANT COMMENT 'The original raw authorization log in its native format',
  resource STRUCT<cloud_partition: STRING, criticality: STRING, data: VARIANT, group: STRUCT<desc: STRING, name: STRING, privileges: ARRAY<STRING>, type: STRING, uid: STRING>, labels: ARRAY<STRING>, name: STRING, namespace: STRING, owner: STRUCT<account: STRUCT<name: STRING, uid: STRING>, domain: STRING, email_addr: STRING, full_name: STRING, groups: ARRAY<STRUCT<desc: STRING, name: STRING, privileges: ARRAY<STRING>, type: STRING, uid: STRING>>, name: STRING, org: STRUCT<name: STRING, ou_name: STRING, ou_uid: STRING, uid: STRING>, type: STRING, type_id: INT, uid: STRING, uid_alt: STRING>, region: STRING, type: STRING, uid: STRING, version: STRING> COMMENT 'The resource being accessed (e.g., S3 bucket, database, API endpoint, network device)',
  service STRUCT<name: STRING, uid: STRING> COMMENT 'The service or application being authorized (e.g., AWS S3, Azure AD, Cisco IOS)',
  session STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING> COMMENT 'Session information including creation time, MFA status, remote/VPN flags',
  severity STRING COMMENT 'The event severity name (e.g., Informational, Low, Medium, High, Critical)',
  severity_id INT COMMENT 'The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other',
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The source endpoint (client making the authorization request)',
  status STRING COMMENT 'The event status name (e.g., Success, Failure)',
  status_code STRING COMMENT 'The vendor-specific authorization status or error code',
  status_detail STRING COMMENT 'Additional details about why authorization was granted or denied',
  status_id INT COMMENT 'The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other',
  time TIMESTAMP COMMENT 'The authorization event time (required field)',
  timezone_offset INT COMMENT 'The timezone offset in minutes from UTC',
  type_name STRING COMMENT 'The event type name, formatted as "Authorize Session: <activity_name>"',
  type_uid BIGINT COMMENT 'The event type unique identifier, calculated as class_uid * 100 + activity_id',
  unmapped VARIANT COMMENT 'Vendor-specific authorization fields that do not map to OCSF schema attributes',
  user STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING> COMMENT 'The user requesting authorization')
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.enableRowTracking' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.domainMetadata' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.rowTracking' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7',
  'delta.parquet.compression.codec' = 'zstd')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.data_security_finding (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity_id INT,
  activity_name STRING,
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>,
  api STRUCT<operation: STRING, request: STRUCT<data: VARIANT, uid: STRING>, response: STRUCT<code: INT, data: VARIANT, error: STRING, message: STRING>>,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING>,
  confidence STRING,
  confidence_id INT,
  confidence_score INT,
  database STRUCT<desc: STRING, modified_time: TIMESTAMP, name: STRING, type: STRING, type_id: INT, uid: STRING>,
  databucket STRUCT<created_time: TIMESTAMP, desc: STRING, file: STRUCT<name: STRING, path: STRING>, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, is_encrypted: BOOLEAN, is_public: BOOLEAN, modified_time: TIMESTAMP, name: STRING, size: BIGINT, type: STRING, type_id: INT, uid: STRING>,
  device STRUCT<created_time: TIMESTAMP, desc: STRING, domain: STRING, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, hostname: STRING, ip: STRING, is_compliant: BOOLEAN, is_managed: BOOLEAN, is_personal: BOOLEAN, is_trusted: BOOLEAN, name: STRING, region: STRING, risk_level: STRING, risk_level_id: INT, risk_score: INT, subnet: STRING, type: STRING, type_id: INT, uid: STRING>,
  disposition STRING,
  disposition_id INT,
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  end_time TIMESTAMP,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  file STRUCT<name: STRING, path: STRING>,
  finding_info STRUCT<analytic: STRUCT<name: STRING, uid: STRING, category: STRING, desc: STRING, related_analytics: ARRAY<VARIANT>, type: STRING, type_id: INT, version: STRING>, attacks: ARRAY<STRUCT<sub_technique: STRUCT<name: STRING, uid: STRING, src_url: STRING>, tactic: STRUCT<name: STRING, uid: STRING, src_url: STRING>, tactics: ARRAY<STRUCT<name: STRING, uid: STRING, src_url: STRING>>, technique: STRUCT<name: STRING, uid: STRING, src_url: STRING>, version: STRING>>, created_time: TIMESTAMP, data_sources: STRING, desc: STRING, first_seen_time: TIMESTAMP, last_seen_time: TIMESTAMP, modified_time: TIMESTAMP, src_url: STRING, title: STRING, uid: STRING>,
  impact STRING,
  impact_id INT,
  impact_score INT,
  is_alert BOOLEAN,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  raw_data VARIANT,
  risk_details STRING,
  risk_level STRING,
  risk_level_id INT,
  risk_score INT,
  severity STRING,
  severity_id INT,
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  table STRUCT<name: STRING, uid: STRING, created_time: TIMESTAMP, desc: STRING, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, modified_time: TIMESTAMP, size: BIGINT>,
  time TIMESTAMP,
  timezone_offset INT,
  type_name STRING,
  unmapped VARIANT)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.datastore_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity_id INT,
  activity_name STRING,
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>,
  api STRUCT<operation: STRING, request: STRUCT<data: VARIANT, uid: STRING>, response: STRUCT<code: INT, data: VARIANT, error: STRING, message: STRING>>,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING>,
  database STRUCT<desc: STRING, modified_time: TIMESTAMP, name: STRING, type: STRING, type_id: INT, uid: STRING>,
  databucket STRUCT<created_time: TIMESTAMP, desc: STRING, file: STRUCT<name: STRING, path: STRING>, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, is_encrypted: BOOLEAN, is_public: BOOLEAN, modified_time: TIMESTAMP, name: STRING, size: BIGINT, type: STRING, type_id: INT, uid: STRING>,
  device STRUCT<created_time: TIMESTAMP, desc: STRING, domain: STRING, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, hostname: STRING, ip: STRING, is_compliant: BOOLEAN, is_managed: BOOLEAN, is_personal: BOOLEAN, is_trusted: BOOLEAN, name: STRING, region: STRING, risk_level: STRING, risk_level_id: INT, risk_score: INT, subnet: STRING, type: STRING, type_id: INT, uid: STRING>,
  disposition STRING,
  disposition_id INT,
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  http_request STRUCT<args: STRING, body_length: INT, http_headers: ARRAY<STRUCT<name: STRING, value: STRING>>, http_method: STRING, length: INT, referrer: STRING, url: STRING, user_agent: STRING, version: STRING>,
  http_response STRUCT<body_length: INT, code: INT, content_type: STRING, http_headers: ARRAY<STRUCT<name: STRING, value: STRING>>, latency: INT, length: INT, message: STRING, status: STRING>,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  raw_data VARIANT,
  severity STRING,
  severity_id INT,
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  table STRUCT<name: STRING, uid: STRING, created_time: TIMESTAMP, desc: STRING, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, modified_time: TIMESTAMP, size: BIGINT>,
  time TIMESTAMP,
  timezone_offset INT,
  type STRING,
  type_id INT,
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.dhcp_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity STRING,
  activity_id INT,
  activity_name STRING,
  app_name STRING,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING>,
  connection_info STRUCT<direction: STRING, direction_id: INT, flag_history: STRING, protocol_name: STRING, protocol_num: INT, protocol_ver: STRING, protocol_ver_id: INT, uid: STRING>,
  disposition STRING,
  disposition_id INT,
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  is_renewal BOOLEAN,
  lease_dur INT,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  raw_data VARIANT,
  severity STRING,
  severity_id INT,
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  time TIMESTAMP,
  timezone_offset INT,
  traffic STRUCT<bytes: BIGINT, bytes_in: BIGINT, bytes_missed: BIGINT, bytes_out: BIGINT, chunks: BIGINT, chunks_in: BIGINT, chunks_out: BIGINT, packets: BIGINT, packets_in: BIGINT, packets_out: BIGINT>,
  transaction_uid STRING,
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

# DNS Activity (Class UID: 4003, Category: Network Activity)
# Tracks DNS query and response events for threat detection and investigation
# Commonly used for: DNS server logs, DNS firewall logs, Zeek/Suricata DNS logs, Cloudflare Gateway, Pi-hole
# Reference: https://schema.ocsf.io/1.3.0/classes/dns_activity
spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.dns_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING COMMENT 'The action taken (e.g., Allowed, Blocked for DNS filtering)',
  action_id INT COMMENT 'The action ID: 0=Unknown, 1=Allowed, 2=Denied/Blocked, 99=Other',
  activity STRING COMMENT 'The DNS activity name (e.g., Query, Response). Normalized value based on activity_id.',
  activity_id INT COMMENT 'The DNS activity ID: 0=Unknown, 1=Query (DNS request), 2=Response (DNS reply), 99=Other',
  activity_name STRING COMMENT 'The DNS activity name (e.g., Query, Response)',
  answers ARRAY<STRUCT<class: STRING, packet_uid: INT, type: STRING, flag_ids: ARRAY<INT>, flags: ARRAY<STRING>, rdata: STRING, ttl: INT>> COMMENT 'DNS response answers. Each answer contains: class (IN/CH), type (A/AAAA/CNAME/MX/TXT), rdata (resolved data), ttl (time-to-live in seconds)',
  app_name STRING COMMENT 'The application name that generated the DNS query (e.g., browser, email client)',
  category_name STRING COMMENT 'The OCSF category name: Network Activity',
  category_uid INT COMMENT 'The OCSF category unique identifier: 4 for Network Activity',
  class_name STRING COMMENT 'The OCSF class name: DNS Activity',
  class_uid INT COMMENT 'The OCSF class unique identifier: 4003 for DNS Activity',
  connection_info STRUCT<direction: STRING, direction_id: INT, flag_history: STRING, protocol_name: STRING, protocol_num: INT, protocol_ver: STRING, protocol_ver_id: INT, uid: STRING> COMMENT 'Connection details: protocol (UDP/TCP), direction, connection UID',
  disposition STRING COMMENT 'The disposition name (e.g., Allowed, Blocked, Sinkholed). For DNS security, indicates if query was blocked/filtered.',
  disposition_id INT COMMENT 'The disposition ID: 0=Unknown, 1=Allowed, 2=Blocked, 3=Quarantined, 4=Isolated, 5=Deleted, 6=Dropped, 99=Other',
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The DNS server (resolver) that handled the query. Includes IP, port (typically 53), hostname.',
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>> COMMENT 'Additional enrichment data from threat intel (e.g., malicious domain indicators), GeoIP, or DNS reputation services',
  message STRING COMMENT 'Human-readable description of the DNS event',
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING> COMMENT 'Event metadata including product info, timestamps, and unique identifiers',
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>> COMMENT 'Observable artifacts extracted from the event: queried domains, resolved IPs, DNS servers - critical for threat hunting and IOC matching',
  policy STRUCT<is_applied: BOOLEAN, name: STRING, uid: STRING, version: STRING> COMMENT 'DNS security policy or filtering rule that was applied (e.g., Cloudflare Gateway policy, Pi-hole blocklist)',
  query STRUCT<class: STRING, packet_uid: INT, type: STRING, hostname: STRING, opcode: STRING, opcode_id: INT> COMMENT 'DNS query details: hostname (FQDN queried), type (A/AAAA/CNAME/MX/TXT/etc), class (usually IN), opcode (QUERY/IQUERY/STATUS)',
  raw_data VARIANT COMMENT 'The original raw DNS log in its native format',
  rcode STRING COMMENT 'DNS response code name (e.g., NoError, NXDomain, ServFail, Refused). Indicates query result status.',
  rcode_id INT COMMENT 'DNS response code ID: 0=NoError (success), 1=FormErr, 2=ServFail, 3=NXDomain (domain not found), 4=NotImp, 5=Refused, 99=Other',
  severity STRING COMMENT 'The event severity name (e.g., Informational, Low, Medium, High, Critical)',
  severity_id INT COMMENT 'The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other',
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The DNS client (source of query). Includes client IP, hostname, port, geolocation.',
  status STRING COMMENT 'The event status name (e.g., Success, Failure)',
  status_code STRING COMMENT 'The vendor-specific status code',
  status_detail STRING COMMENT 'Additional details about the DNS query/response status',
  status_id INT COMMENT 'The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other',
  time TIMESTAMP COMMENT 'The DNS query time (required field)',
  timezone_offset INT COMMENT 'The timezone offset in minutes from UTC',
  traffic STRUCT<bytes: BIGINT, bytes_in: BIGINT, bytes_missed: BIGINT, bytes_out: BIGINT, chunks: BIGINT, chunks_in: BIGINT, chunks_out: BIGINT, packets: BIGINT, packets_in: BIGINT, packets_out: BIGINT> COMMENT 'DNS traffic statistics (bytes/packets for query and response)',
  type_name STRING COMMENT 'The event type name, formatted as "DNS Activity: <activity_name>"',
  type_uid BIGINT COMMENT 'The event type unique identifier, calculated as class_uid * 100 + activity_id',
  unmapped VARIANT COMMENT 'Vendor-specific DNS fields that do not map to OCSF schema attributes (e.g., DNS flags, EDNS options)')
USING delta
COMMENT 'DNS Activity events capture DNS queries and responses for security monitoring, threat detection (e.g., DNS tunneling, DGA domains, C2 communication), and performance analysis. Critical for detecting malware, data exfiltration, and unauthorized DNS usage.'
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.email_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity STRING,
  activity_id INT,
  activity_name STRING,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  direction STRING,
  direction_id INT,
  disposition STRING,
  disposition_id INT,
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  email STRUCT<to: STRING>,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  message STRING,
  message_trace_uid STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  protocol_name STRING,
  raw_data VARIANT,
  severity STRING,
  severity_id INT,
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  time TIMESTAMP,
  timezone_offset INT,
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.entity_management (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  access_list ARRAY<STRING>,
  access_mask INT,
  action STRING,
  action_id INT,
  activity_id INT,
  activity_name STRING,
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>,
  api STRUCT<operation: STRING, request: STRUCT<data: VARIANT, uid: STRING>, response: STRUCT<code: INT, data: VARIANT, error: STRING, message: STRING>>,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING>,
  comment STRING,
  device STRUCT<created_time: TIMESTAMP, desc: STRING, domain: STRING, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, hostname: STRING, ip: STRING, is_compliant: BOOLEAN, is_managed: BOOLEAN, is_personal: BOOLEAN, is_trusted: BOOLEAN, name: STRING, region: STRING, risk_level: STRING, risk_level_id: INT, risk_score: INT, subnet: STRING, type: STRING, type_id: INT, uid: STRING>,
  disposition STRING,
  disposition_id INT,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  entity STRUCT<name: STRING, uid: STRING, data: VARIANT, email: STRUCT<to: STRING>, group: STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, policies: ARRAY<STRUCT<is_applied: BOOLEAN, name: STRING, uid: STRING, version: STRING>>, type: STRING, type_id: INT, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>, version: STRING>,
  entity_result STRUCT<name: STRING, uid: STRING, data: VARIANT, email: STRUCT<to: STRING>, group: STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, policies: ARRAY<STRUCT<is_applied: BOOLEAN, name: STRING, uid: STRING, version: STRING>>, type: STRING, type_id: INT, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>, version: STRING>,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  raw_data VARIANT,
  severity STRING,
  severity_id INT,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  time TIMESTAMP,
  timezone_offset INT,
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

# File Activity (Class UID: 1001, Category: System Activity)
# Tracks file system operations (create, read, write, delete, rename, etc.)
# Commonly used for: File integrity monitoring (FIM), DLP logs, EDR file events, audit logs
# Reference: https://schema.ocsf.io/1.3.0/classes/file_activity
spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.file_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  access_mask INT COMMENT 'The Windows access mask indicating requested file permissions (e.g., READ_DATA, WRITE_DATA, DELETE)',
  action STRING COMMENT 'The action taken on the file operation (e.g., Allowed, Blocked, Quarantined)',
  action_id INT COMMENT 'The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other',
  activity STRING COMMENT 'The file activity name (e.g., Create, Read, Write, Delete, Rename). Normalized value based on activity_id.',
  activity_id INT COMMENT 'The file activity ID: 0=Unknown, 1=Create, 2=Read, 3=Write, 4=Rename, 5=Delete, 6=Mount, 7=Unmount, 8=Encrypt, 9=Decrypt, 10=Open, 11=Modify Permissions, 99=Other',
  activity_name STRING COMMENT 'The file activity name (e.g., Create, Delete, Modify)',
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>> COMMENT 'The actor (process or user) that performed the file operation',
  category_name STRING COMMENT 'The OCSF category name: System Activity',
  category_uid INT COMMENT 'The OCSF category unique identifier: 1 for System Activity',
  class_name STRING COMMENT 'The OCSF class name: File Activity',
  class_uid INT COMMENT 'The OCSF class unique identifier: 1001 for File Activity',
  component STRING COMMENT 'The system component that generated the file event (e.g., kernel, filesystem driver)',
  device STRUCT<created_time: TIMESTAMP, desc: STRING, domain: STRING, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, hostname: STRING, ip: STRING, is_compliant: BOOLEAN, is_managed: BOOLEAN, is_personal: BOOLEAN, is_trusted: BOOLEAN, name: STRING, region: STRING, risk_level: STRING, risk_level_id: INT, risk_score: INT, subnet: STRING, type: STRING, type_id: INT, uid: STRING> COMMENT 'The device/host where the file operation occurred',
  disposition STRING COMMENT 'The disposition name (e.g., Allowed, Blocked, Quarantined). For DLP/security, indicates if file operation was allowed or prevented.',
  disposition_id INT COMMENT 'The disposition ID: 0=Unknown, 1=Allowed, 2=Blocked, 3=Quarantined, 4=Isolated, 5=Deleted, 99=Other',
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>> COMMENT 'Additional enrichment data from threat intel (e.g., malicious file hashes), malware scanning results',
  file STRUCT<name: STRING, path: STRING> COMMENT 'The file details: filename, full path, extension, size, hashes (MD5/SHA1/SHA256)',
  file_diff STRING COMMENT 'The file content changes (diff) for file integrity monitoring',
  message STRING COMMENT 'Human-readable description of the file event',
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING> COMMENT 'Event metadata including product info, timestamps, and unique identifiers',
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>> COMMENT 'Observable artifacts: file paths, hashes, process names - critical for threat hunting and IOC matching',
  raw_data VARIANT COMMENT 'The original raw file activity log in its native format',
  severity STRING COMMENT 'The event severity name (e.g., Informational, Low, Medium, High, Critical)',
  severity_id INT COMMENT 'The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other',
  status STRING COMMENT 'The event status name (e.g., Success, Failure)',
  status_code STRING COMMENT 'The vendor-specific status or error code',
  status_detail STRING COMMENT 'Additional details about the file operation status',
  status_id INT COMMENT 'The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other',
  time TIMESTAMP COMMENT 'The file operation time (required field)',
  timezone_offset INT COMMENT 'The timezone offset in minutes from UTC',
  type_name STRING COMMENT 'The event type name, formatted as "File Activity: <activity_name>"',
  type_uid BIGINT COMMENT 'The event type unique identifier, calculated as class_uid * 100 + activity_id',
  unmapped VARIANT COMMENT 'Vendor-specific file activity fields that do not map to OCSF schema attributes')
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7',
  'delta.workloadBasedColumns.optimizerStatistics' = '`raw_data`')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.group_management (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity STRING,
  activity_id INT,
  activity_name STRING,
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>,
  api STRUCT<operation: STRING, request: STRUCT<data: VARIANT, uid: STRING>, response: STRUCT<code: INT, data: VARIANT, error: STRING, message: STRING>>,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING>,
  disposition STRING,
  disposition_id INT,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  group STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  privileges ARRAY<STRING>,
  raw_data VARIANT,
  resource STRUCT<hostname: STRING, ip: STRING, name: STRING, uid: STRING>,
  severity STRING,
  severity_id INT,
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  time TIMESTAMP,
  timezone_offset INT,
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT,
  user STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

# HTTP Activity (Class UID: 4002, Category: Network Activity)
# Tracks HTTP/HTTPS requests and responses for web traffic monitoring and API activity
# Commonly used for: Web proxy logs, API gateway logs, WAF logs, load balancer logs
# Reference: https://schema.ocsf.io/1.3.0/classes/http_activity
spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.http_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING COMMENT 'The action taken on the HTTP request (e.g., Allowed, Blocked, Redirected)',
  action_id INT COMMENT 'The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other',
  activity STRING COMMENT 'The HTTP activity name (e.g., Request, Response, Upload, Download). Normalized value based on activity_id.',
  activity_id INT COMMENT 'The HTTP activity ID: 0=Unknown, 1=Request, 2=Response, 3=Upload, 4=Download, 5=Send, 6=Receive, 99=Other',
  activity_name STRING COMMENT 'The HTTP activity name',
  app_name STRING COMMENT 'The application name that generated the HTTP traffic (e.g., browser, mobile app, API client)',
  category_name STRING COMMENT 'The OCSF category name: Network Activity',
  category_uid INT COMMENT 'The OCSF category unique identifier: 4 for Network Activity',
  class_name STRING COMMENT 'The OCSF class name: HTTP Activity',
  class_uid INT COMMENT 'The OCSF class unique identifier: 4002 for HTTP Activity',
  connection_info STRUCT<direction: STRING, direction_id: INT, flag_history: STRING, protocol_name: STRING, protocol_num: INT, protocol_ver: STRING, protocol_ver_id: INT, uid: STRING> COMMENT 'Connection details: protocol (HTTP/HTTPS), direction, connection UID',
  disposition STRING COMMENT 'The disposition name (e.g., Allowed, Blocked, Quarantined). For web security, indicates if request was blocked/filtered.',
  disposition_id INT COMMENT 'The disposition ID: 0=Unknown, 1=Allowed, 2=Blocked, 3=Quarantined, 99=Other',
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The destination web server. Includes IP, port (80/443), hostname, geolocation.',
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>> COMMENT 'Additional enrichment data from threat intel (e.g., malicious URL indicators), GeoIP, or reputation services',
  file STRUCT<name: STRING, path: STRING> COMMENT 'The file being accessed via HTTP (for file downloads/uploads)',
  firewall_rule STRUCT<name: STRING, uid: STRING, category: STRING, desc: STRING, type: STRING, version: STRING, condition: STRING, duration: BIGINT, match_details: ARRAY<STRING>, match_location: STRING, rate_limit: INT, sensitivity: STRING> COMMENT 'Web application firewall (WAF) rule that matched this request',
  http_cookies ARRAY<STRUCT<domain: STRING, expiration_time: TIMESTAMP, http_only: BOOLEAN, is_http_only: BOOLEAN, is_secure: BOOLEAN, name: STRING, path: STRING, samesite: STRING, secure: BOOLEAN, value: STRING>> COMMENT 'HTTP cookies sent/received. Includes security flags (httpOnly, secure, samesite)',
  http_request STRUCT<args: STRING, body_length: INT, http_headers: ARRAY<STRUCT<name: STRING, value: STRING>>, http_method: STRING, length: INT, referrer: STRING, url: STRING, user_agent: STRING, version: STRING> COMMENT 'HTTP request details: method (GET/POST/PUT/DELETE), URL, headers, user-agent, referrer, query args',
  http_response STRUCT<body_length: INT, code: INT, content_type: STRING, http_headers: ARRAY<STRUCT<name: STRING, value: STRING>>, latency: INT, length: INT, message: STRING, status: STRING> COMMENT 'HTTP response details: status code (200/404/500), content-type, response size, latency in ms',
  message STRING COMMENT 'Human-readable description of the HTTP event',
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING> COMMENT 'Event metadata including product info, timestamps, and unique identifiers',
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>> COMMENT 'Observable artifacts: URLs, domains, IPs, user-agents - critical for threat hunting and IOC matching',
  policy STRUCT<is_applied: BOOLEAN, name: STRING, uid: STRING, version: STRING> COMMENT 'Web security policy or WAF rule that was applied',
  raw_data VARIANT COMMENT 'The original raw HTTP log in its native format',
  severity STRING COMMENT 'The event severity name (e.g., Informational, Low, Medium, High, Critical)',
  severity_id INT COMMENT 'The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other',
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The HTTP client (source of request). Includes client IP, hostname, port, geolocation.',
  status STRING COMMENT 'The event status name (e.g., Success, Failure)',
  status_code STRING COMMENT 'The vendor-specific status code',
  status_detail STRING COMMENT 'Additional details about the HTTP status',
  status_id INT COMMENT 'The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other',
  time TIMESTAMP COMMENT 'The HTTP request time (required field)',
  timezone_offset INT COMMENT 'The timezone offset in minutes from UTC',
  traffic STRUCT<bytes: BIGINT, bytes_in: BIGINT, bytes_missed: BIGINT, bytes_out: BIGINT, chunks: BIGINT, chunks_in: BIGINT, chunks_out: BIGINT, packets: BIGINT, packets_in: BIGINT, packets_out: BIGINT> COMMENT 'HTTP traffic statistics: request size (bytes_out), response size (bytes_in), total bytes',
  type_name STRING COMMENT 'The event type name, formatted as "HTTP Activity: <activity_name>"',
  type_uid BIGINT COMMENT 'The event type unique identifier, calculated as class_uid * 100 + activity_id',
  unmapped VARIANT COMMENT 'Vendor-specific HTTP fields that do not map to OCSF schema attributes')
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7',
  'delta.workloadBasedColumns.optimizerStatistics' = '`time`')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.kernel_extension_activity (
  dsl_id STRING,
  time TIMESTAMP,
  class_name STRING,
  type_uid BIGINT,
  category_name STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, profiles: ARRAY<STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  severity STRING,
  severity_id INT,
  class_uid INT,
  actor STRUCT<process: STRUCT<tid: INT, pid: INT>>,
  category_uid INT,
  activity_id INT,
  driver STRUCT<file: STRUCT<path: STRING, name: STRING>>,
  type_name STRING,
  start_time TIMESTAMP,
  activity_name STRING)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

# Network Activity (Class UID: 4001, Category: Network Activity)
# Tracks network connection and traffic events (open, close, traffic flow, etc.)
# Commonly used for: Zeek conn logs, firewall logs, VPC flow logs, network device logs
# Reference: https://schema.ocsf.io/1.3.0/classes/network_activity
spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.network_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING COMMENT 'The action taken by the network device (e.g., Allowed, Denied, Dropped)',
  action_id INT COMMENT 'The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other',
  activity STRING COMMENT 'The network activity name (e.g., Open, Close, Traffic, Fail). Normalized value based on activity_id.',
  activity_id INT COMMENT 'The network activity ID: 0=Unknown, 1=Open (connection established), 2=Close (connection terminated), 3=Refuse (connection refused), 4=Fail, 5=Traffic (data flow), 6=Scan, 7=Probe, 99=Other',
  activity_name STRING COMMENT 'The network activity name (e.g., Open, Close, Traffic)',
  category_name STRING COMMENT 'The OCSF category name: Network Activity',
  category_uid INT COMMENT 'The OCSF category unique identifier: 4 for Network Activity',
  class_name STRING COMMENT 'The OCSF class name: Network Activity',
  class_uid INT COMMENT 'The OCSF class unique identifier: 4001 for Network Activity',
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING> COMMENT 'Cloud environment information (AWS, Azure, GCP)',
  connection_info STRUCT<direction: STRING, direction_id: INT, flag_history: STRING, protocol_name: STRING, protocol_num: INT, protocol_ver: STRING, protocol_ver_id: INT, uid: STRING> COMMENT 'Connection details: direction (Inbound/Outbound), protocol (TCP/UDP/ICMP), TCP flags, connection UID',
  disposition STRING,
  disposition_id INT,
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The destination endpoint (server/responder). Includes IP, port, hostname, geolocation.',
  end_time TIMESTAMP COMMENT 'The connection end/close time',
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>> COMMENT 'Additional enrichment data from threat intel, GeoIP, or other sources',
  message STRING COMMENT 'Human-readable description of the network event',
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING> COMMENT 'Event metadata including product info, timestamps, and unique identifiers',
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>> COMMENT 'Observable artifacts extracted from the event (IPs, domains, ports, protocols) for threat hunting',
  policy STRUCT<is_applied: BOOLEAN, name: STRING, uid: STRING, version: STRING> COMMENT 'Network policy or firewall rule that was applied to this connection',
  raw_data VARIANT COMMENT 'The original raw event data in its native format',
  severity STRING COMMENT 'The event severity name (e.g., Informational, Low, Medium, High, Critical)',
  severity_id INT COMMENT 'The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other',
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING> COMMENT 'The source endpoint (client/initiator). Includes IP, port, hostname, geolocation.',
  start_time TIMESTAMP COMMENT 'The connection start/open time',
  status STRING COMMENT 'The event status name (e.g., Success, Failure)',
  status_code STRING COMMENT 'The vendor-specific status or connection state code (e.g., Zeek conn_state)',
  status_detail STRING COMMENT 'Additional details about the connection status or state',
  status_id INT COMMENT 'The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other',
  time TIMESTAMP COMMENT 'The event occurrence time (typically connection start or log time)',
  timezone_offset INT COMMENT 'The timezone offset in minutes from UTC',
  tls STRUCT<alert: INT, certificate: STRUCT<created_time: TIMESTAMP, expiration_time: TIMESTAMP, fingerprints: ARRAY<STRUCT<algorithm: STRING, algorithm_id: INT, value: STRING>>, issuer: STRING, serial_number: STRING, subject: STRING, version: STRING>, certificate_chain: ARRAY<STRING>, cipher: STRING, client_ciphers: ARRAY<STRING>, handshake_dur: INT, ja3_hash: STRUCT<algorithm: STRING, algorithm_id: INT, value: STRING>, ja3s_hash: STRUCT<algorithm: STRING, algorithm_id: INT, value: STRING>, key_length: INT, server_ciphers: ARRAY<STRING>, sni: STRING, tls_extension_list: ARRAY<STRUCT<type: STRING, type_id: INT, data: STRING>>, version: STRING> COMMENT 'TLS protocol information including cipher suite, certificate details, JA3/JA3S fingerprints, and Server Name Indication (SNI)',
  traffic STRUCT<bytes: BIGINT, bytes_in: BIGINT, bytes_missed: BIGINT, bytes_out: BIGINT, chunks: BIGINT, chunks_in: BIGINT, chunks_out: BIGINT, packets: BIGINT, packets_in: BIGINT, packets_out: BIGINT> COMMENT 'Traffic statistics: bytes and packets transmitted in both directions',
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT,
  url STRUCT<url_string: STRING>)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7',
  'delta.workloadBasedColumns.optimizerStatistics' = '`time`')
""")

# COMMAND ----------

# Process Activity (Class UID: 1007, Category: System Activity)
# Tracks process lifecycle events (launch, terminate, injection, etc.)
# Commonly used for: EDR logs, Windows Security logs, Sysmon, auditd, system monitoring
# Reference: https://schema.ocsf.io/1.3.0/classes/process_activity
spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.process_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING COMMENT 'The action taken on the process (e.g., Allowed, Blocked, Terminated)',
  action_id INT COMMENT 'The action ID: 0=Unknown, 1=Allowed, 2=Denied, 99=Other',
  activity STRING COMMENT 'The process activity name (e.g., Launch, Terminate, Inject). Normalized value based on activity_id.',
  activity_id INT COMMENT 'The process activity ID: 0=Unknown, 1=Launch (process started), 2=Terminate (process ended), 3=Open (process handle opened), 4=Inject (code injection), 5=Set User ID, 6=Rename, 99=Other',
  activity_name STRING COMMENT 'The process activity name (e.g., Launch, Terminate)',
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>> COMMENT 'The actor (parent process or user) that initiated the process activity',
  category_name STRING COMMENT 'The OCSF category name: System Activity',
  category_uid INT COMMENT 'The OCSF category unique identifier: 1 for System Activity',
  class_name STRING COMMENT 'The OCSF class name: Process Activity',
  class_uid INT COMMENT 'The OCSF class unique identifier: 1007 for Process Activity',
  device STRUCT<created_time: TIMESTAMP, desc: STRING, domain: STRING, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, hostname: STRING, ip: STRING, is_compliant: BOOLEAN, is_managed: BOOLEAN, is_personal: BOOLEAN, is_trusted: BOOLEAN, name: STRING, region: STRING, risk_level: STRING, risk_level_id: INT, risk_score: INT, subnet: STRING, type: STRING, type_id: INT, uid: STRING> COMMENT 'The device/host where the process activity occurred',
  disposition STRING COMMENT 'The disposition name (e.g., Allowed, Blocked, Quarantined). For EDR, indicates if process was allowed to run or blocked.',
  disposition_id INT COMMENT 'The disposition ID: 0=Unknown, 1=Allowed, 2=Blocked, 3=Quarantined, 4=Isolated, 5=Deleted, 99=Other',
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>> COMMENT 'Additional enrichment data from threat intel (e.g., malicious process hashes), behavioral analysis',
  exit_code INT COMMENT 'The process exit code (0=success, non-zero=error)',
  injection_type STRING COMMENT 'The type of code injection technique used (e.g., DLL Injection, Process Hollowing, Thread Execution Hijacking)',
  injection_type_id INT COMMENT 'The injection type ID: 0=Unknown, 1=CreateRemoteThread, 2=QueueUserAPC, 3=SetWindowsHookEx, 4=Process Hollowing, 5=AppInit DLLs, 99=Other',
  message STRING COMMENT 'Human-readable description of the process event',
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING> COMMENT 'Event metadata including product info, timestamps, and unique identifiers',
  module STRUCT<base_address: STRING, file: STRUCT<name: STRING, path: STRING>, function_name: STRING, load_type: STRING, load_type_id: INT, start_address: STRING, type: STRING> COMMENT 'Module/DLL loaded by the process. Includes file path, load address, load type.',
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>> COMMENT 'Observable artifacts: process names, file hashes, command lines, parent processes - critical for threat hunting',
  process STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>> COMMENT 'The process details: name, PID, command line, parent PID, user, session info',
  raw_data VARIANT COMMENT 'The original raw process log in its native format',
  requested_permissions INT COMMENT 'The access rights/permissions requested for the process',
  severity STRING COMMENT 'The event severity name (e.g., Informational, Low, Medium, High, Critical)',
  severity_id INT COMMENT 'The event severity ID: 0=Unknown, 1=Informational, 2=Low, 3=Medium, 4=High, 5=Critical, 6=Fatal, 99=Other',
  status STRING COMMENT 'The event status name (e.g., Success, Failure)',
  status_code STRING COMMENT 'The vendor-specific status or error code',
  status_detail STRING COMMENT 'Additional details about the process status',
  status_id INT COMMENT 'The event status ID: 0=Unknown, 1=Success, 2=Failure, 99=Other',
  time TIMESTAMP COMMENT 'The process event time (required field)',
  timezone_offset INT COMMENT 'The timezone offset in minutes from UTC',
  type_name STRING COMMENT 'The event type name, formatted as "Process Activity: <activity_name>"',
  type_uid BIGINT COMMENT 'The event type unique identifier, calculated as class_uid * 100 + activity_id',
  unmapped VARIANT COMMENT 'Vendor-specific process fields that do not map to OCSF schema attributes')
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.scheduled_job_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity STRING,
  activity_id INT,
  activity_name STRING,
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  device STRUCT<created_time: TIMESTAMP, desc: STRING, domain: STRING, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, hostname: STRING, ip: STRING, is_compliant: BOOLEAN, is_managed: BOOLEAN, is_personal: BOOLEAN, is_trusted: BOOLEAN, name: STRING, region: STRING, risk_level: STRING, risk_level_id: INT, risk_score: INT, subnet: STRING, type: STRING, type_id: INT, uid: STRING>,
  disposition STRING,
  disposition_id INT,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  job STRUCT<cmd_line: STRING, created_time: TIMESTAMP, desc: STRING, file: STRUCT<name: STRING, path: STRING>, last_run_time: TIMESTAMP, name: STRING, next_run_time: TIMESTAMP, run_state: STRING, run_state_id: INT, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  raw_data VARIANT,
  risk_details STRING,
  risk_level STRING,
  risk_level_id INT,
  risk_score INT,
  severity STRING,
  severity_id INT,
  start_time TIMESTAMP,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  time TIMESTAMP,
  timezone_offset INT,
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.script_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity STRING,
  activity_id INT,
  activity_name STRING,
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  device STRUCT<created_time: TIMESTAMP, desc: STRING, domain: STRING, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, hostname: STRING, ip: STRING, is_compliant: BOOLEAN, is_managed: BOOLEAN, is_personal: BOOLEAN, is_trusted: BOOLEAN, name: STRING, region: STRING, risk_level: STRING, risk_level_id: INT, risk_score: INT, subnet: STRING, type: STRING, type_id: INT, uid: STRING>,
  disposition STRING,
  disposition_id INT,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  raw_data VARIANT,
  script STRUCT<file: STRUCT<name: STRING, path: STRING>, hashes: ARRAY<STRUCT<algorithm: STRING, algorithm_id: INT, value: STRING>>, name: STRING, parent_uid: STRING, script_content: STRUCT<is_truncated: BOOLEAN, untruncated_size: INT, value: STRING>, type: STRING, type_id: INT, uid: STRING>,
  severity STRING,
  severity_id INT,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  time TIMESTAMP,
  timezone_offset INT,
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.ssh_activity (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity_id INT,
  activity_name STRING,
  app_name STRING,
  auth_type STRING,
  auth_type_id INT,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  connection_info STRUCT<direction: STRING, direction_id: INT, flag_history: STRING, protocol_name: STRING, protocol_num: INT, protocol_ver: STRING, protocol_ver_id: INT, uid: STRING>,
  disposition STRING,
  disposition_id INT,
  dst_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  file STRUCT<name: STRING, path: STRING>,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  protocol_ver STRING,
  raw_data VARIANT,
  severity STRING,
  severity_id INT,
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  time TIMESTAMP,
  timezone_offset INT,
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.user_access (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity STRING,
  activity_id INT,
  activity_name STRING,
  actor STRUCT<app_name: STRING, app_uid: STRING, authorizations: ARRAY<STRUCT<decision: STRING>>, idp: STRUCT<domain: STRING, name: STRING, protocol_name: STRING, tenant_uid: STRING, uid: STRING>, process: STRUCT<cmd_line: STRING, cpid: STRING, name: STRING, pid: INT, session: STRUCT<created_time: TIMESTAMP, credential_uid: STRING, expiration_reason: STRING, expiration_time: TIMESTAMP, is_mfa: BOOLEAN, is_remote: BOOLEAN, is_vpn: BOOLEAN, issuer: STRING, terminal: STRING, uid: STRING, uid_alt: STRING, uuid: STRING>, uid: STRING, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>, user: STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>>,
  api STRUCT<operation: STRING, request: STRUCT<data: VARIANT, uid: STRING>, response: STRUCT<code: INT, data: VARIANT, error: STRING, message: STRING>>,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  cloud STRUCT<account: STRUCT<name: STRING, uid: STRING>, cloud_partition: STRING, project_uid: STRING, provider: STRING, region: STRING, zone: STRING>,
  disposition STRING,
  disposition_id INT,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  privileges ARRAY<STRING>,
  raw_data VARIANT,
  resource STRUCT<hostname: STRING, ip: STRING, name: STRING, uid: STRING>,
  severity STRING,
  severity_id INT,
  src_endpoint STRUCT<domain: STRING, hostname: STRING, instance_uid: STRING, interface_name: STRING, interface_uid: STRING, ip: STRING, name: STRING, port: INT, svc_name: STRING, type: STRING, type_id: INT, uid: STRING, location: STRUCT<city: STRING, continent: STRING, country: STRING, lat: FLOAT, long: FLOAT, postal_code: STRING>, mac: STRING, vpc_uid: STRING, zone: STRING>,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  time TIMESTAMP,
  timezone_offset INT,
  type_name STRING,
  type_uid BIGINT,
  unmapped VARIANT,
  user STRUCT<has_mfa: BOOLEAN, name: STRING, type: STRING, type_id: INT, uid: STRING>)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.feature.variantShredding-preview' = "supported",
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE `{catalog_name}`.`{gold_database}`.vulnerability_finding (
  dsl_id STRING NOT NULL COMMENT 'Unique ID generated and maintained by Databricks Security Lakehouse for data lineage from ingestion throughout all medallion layers.',
  action STRING,
  action_id INT,
  activity STRING,
  activity_id INT,
  activity_name STRING,
  category_name STRING,
  category_uid INT,
  class_name STRING,
  class_uid INT,
  device STRUCT<created_time: TIMESTAMP, desc: STRING, domain: STRING, groups: ARRAY<STRUCT<name: STRING, privileges: STRING, type: STRING, uid: STRING>>, hostname: STRING, ip: STRING, is_compliant: BOOLEAN, is_managed: BOOLEAN, is_personal: BOOLEAN, is_trusted: BOOLEAN, name: STRING, region: STRING, risk_level: STRING, risk_level_id: INT, risk_score: INT, subnet: STRING, type: STRING, type_id: INT, uid: STRING>,
  disposition STRING,
  disposition_id INT,
  end_time TIMESTAMP,
  enrichments ARRAY<STRUCT<data: VARIANT, desc: STRING, name: STRING, value: STRING>>,
  finding_info STRUCT<analytic: STRUCT<name: STRING, uid: STRING, category: STRING, desc: STRING, related_analytics: ARRAY<VARIANT>, type: STRING, type_id: INT, version: STRING>, attacks: ARRAY<STRUCT<sub_technique: STRUCT<name: STRING, uid: STRING, src_url: STRING>, tactic: STRUCT<name: STRING, uid: STRING, src_url: STRING>, tactics: ARRAY<STRUCT<name: STRING, uid: STRING, src_url: STRING>>, technique: STRUCT<name: STRING, uid: STRING, src_url: STRING>, version: STRING>>, created_time: TIMESTAMP, data_sources: STRING, desc: STRING, first_seen_time: TIMESTAMP, last_seen_time: TIMESTAMP, modified_time: TIMESTAMP, src_url: STRING, title: STRING, uid: STRING>,
  message STRING,
  metadata STRUCT<correlation_uid: STRING, event_code: STRING, log_level: STRING, log_name: STRING, log_provider: STRING, log_format: STRING, log_version: STRING, logged_time: TIMESTAMP, modified_time: TIMESTAMP, original_time: STRING, processed_time: TIMESTAMP, product: STRUCT<name: STRING, vendor_name: STRING, version: STRING>, tags: VARIANT, tenant_uid: STRING, uid: STRING, version: STRING>,
  observables ARRAY<STRUCT<name: STRING, type: STRING, value: STRING>>,
  raw_data VARIANT,
  resources ARRAY<STRUCT<hostname: STRING, ip: STRING, name: STRING, uid: STRING>>,
  severity STRING,
  severity_id INT,
  start_time TIMESTAMP,
  status STRING,
  status_code STRING,
  status_detail STRING,
  status_id INT,
  time TIMESTAMP,
  timezone_offset INT,
  type_name STRING,
  unmapped VARIANT,
  vulnerabilities ARRAY<STRUCT<cve: STRUCT<created_time: TIMESTAMP, cvss: ARRAY<STRUCT<base_score: FLOAT, overall_score: FLOAT, severity: STRING, src_url: STRING>>, uid: STRING>, desc: STRING, exploit_last_seen_time: TIMESTAMP, first_seen_time: TIMESTAMP, fix_available: BOOLEAN, is_exploit_available: BOOLEAN, is_fix_available: BOOLEAN>>)
USING delta
TBLPROPERTIES (
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.appendOnly' = 'supported',
  'delta.feature.deletionVectors' = 'supported',
  'delta.feature.invariants' = 'supported',
  'delta.feature.variantType-preview' = 'supported',
  'delta.minReaderVersion' = '3',
  'delta.minWriterVersion' = '7')
""")