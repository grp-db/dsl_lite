# OCSF Numeric ID Reference

Quick reference for OCSF `*_id` fields used across tables. Use when mapping or decoding events in YAML or queries.

---

## Common (multiple tables)

### action_id

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Allowed |
| 2 | Denied (or Blocked) |
| 99 | Other |

### status_id

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Success |
| 2 | Failure |
| 99 | Other |

### severity_id

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Informational |
| 2 | Low |
| 3 | Medium |
| 4 | High |
| 5 | Critical |
| 6 | Fatal |
| 99 | Other |

### disposition_id

Used in Network Activity, Authentication, File Activity, Process Activity, and others. Some tables use a subset.

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Allowed |
| 2 | Blocked |
| 3 | Quarantined |
| 4 | Isolated |
| 5 | Deleted |
| 6 | Dropped |
| 7 | Custom Action |
| 8 | Approved |
| 9 | Restored |
| 10 | Exonerated |
| 99 | Other |

---

## activity_id (by class)

*`type_uid` = class_uid × 100 + activity_id*

### Network Activity (class_uid 4001)

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Open (connection established) |
| 2 | Close (connection terminated) |
| 3 | Refuse (connection refused) |
| 4 | Fail |
| 5 | Traffic (data flow) |
| 6 | Scan |
| 7 | Probe |
| 99 | Other |

### DNS Activity (class_uid 4003)

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Query (DNS request) |
| 2 | Response (DNS reply) |
| 99 | Other |

### HTTP Activity (class_uid 4002)

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Request |
| 2 | Response |
| 3 | Upload |
| 4 | Download |
| 5 | Send |
| 6 | Receive |
| 99 | Other |

### Authentication (class_uid 3002)

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Logon |
| 2 | Logoff |
| 3 | Authentication Ticket |
| 4 | Service Ticket Request |
| 99 | Other |

### Authorize Session (class_uid 3003)

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Assign Privileges |
| 2 | Revoke Privileges |
| 99 | Other |

### Process Activity (class_uid 1007)

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Launch (process started) |
| 2 | Terminate (process ended) |
| 3 | Open (process handle opened) |
| 4 | Inject (code injection) |
| 5 | Set User ID |
| 6 | Rename |
| 99 | Other |

### File Activity (class_uid 1001)

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Create |
| 2 | Read |
| 3 | Write |
| 4 | Rename |
| 5 | Delete |
| 6 | Mount |
| 7 | Unmount |
| 8 | Encrypt |
| 9 | Decrypt |
| 10 | Open |
| 11 | Modify Permissions |
| 99 | Other |

### Account Change (class_uid 3001)

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | Create |
| 2 | Enable |
| 3 | Password Change |
| 4 | Password Reset |
| 5 | Disable |
| 6 | Delete |
| 7 | Attach Policy |
| 8 | Detach Policy |
| 9 | Lock |
| 10 | MFA Enable |
| 11 | MFA Disable |
| 99 | Other |

---

## DNS-specific

### rcode_id (DNS response code)

| ID | Name |
|----|------|
| 0 | NoError (success) |
| 1 | FormErr |
| 2 | ServFail |
| 3 | NXDomain (domain not found) |
| 4 | NotImp |
| 5 | Refused |
| 99 | Other |

---

## Authentication-specific

### auth_protocol_id

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | NTLM |
| 2 | Kerberos |
| 3 | Digest |
| 4 | OpenID |
| 5 | SAML |
| 6 | OAuth |
| 7 | SSO |
| 8 | CHAP |
| 9 | PAP |
| 10 | RADIUS |
| 11 | LDAP |
| 99 | Other |

### logon_type_id (Windows)

| ID | Name |
|----|------|
| 0 | Unknown |
| 2 | Interactive |
| 3 | Network |
| 4 | Batch |
| 5 | Service |
| 7 | Unlock |
| 8 | NetworkCleartext |
| 9 | NewCredentials |
| 10 | RemoteInteractive |
| 11 | CachedInteractive |
| 99 | Other |

---

## Process Activity–specific

### injection_type_id

| ID | Name |
|----|------|
| 0 | Unknown |
| 1 | CreateRemoteThread |
| 2 | QueueUserAPC |
| 3 | SetWindowsHookEx |
| 4 | Process Hollowing |
| 5 | AppInit DLLs |
| 99 | Other |

---

## OCSF category_uid (high-level)

| UID | Category |
|-----|----------|
| 1 | System Activity |
| 2 | Findings |
| 3 | Identity & Access Management |
| 4 | Network Activity |
| 5 | Discovery |
| 6 | Application Activity |

## OCSF class_uid (tables in this repo)

| UID | Class |
|-----|-------|
| 1001 | File Activity |
| 1007 | Process Activity |
| 3001 | Account Change |
| 3002 | Authentication |
| 3003 | Authorize Session |
| 4001 | Network Activity |
| 4002 | HTTP Activity |
| 4003 | DNS Activity |
