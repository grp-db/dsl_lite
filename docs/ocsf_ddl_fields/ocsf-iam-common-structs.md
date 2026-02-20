# OCSF IAM Common Structs Reference

Three small structs are shared across Identity & Access Management (and sometimes other) tables: **session**, **user**, and **service**. They also appear nested (e.g. **user** and **session** inside **actor** / **process**). Use this reference when mapping auth, authorization, or session data.

---

## session

**Type:** `STRUCT<...>`

Session information: creation time, expiration, MFA/remote/VPN flags, and identifiers. Used as top-level **`session`** in authentication and authorize_session, and nested inside **actor.process** in many tables.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `created_time` | TIMESTAMP | When the session was created. |
| `credential_uid` | STRING | Credential or token identifier. |
| `expiration_reason` | STRING | Reason the session ended (if applicable). |
| `expiration_time` | TIMESTAMP | When the session expires or expired. |
| `is_mfa` | BOOLEAN | Whether MFA was used for this session. |
| `is_remote` | BOOLEAN | Whether the session is remote. |
| `is_vpn` | BOOLEAN | Whether the session is over VPN. |
| `issuer` | STRING | Session or token issuer. |
| `terminal` | STRING | Terminal or client identifier. |
| `uid` | STRING | Session unique identifier. |
| `uid_alt` | STRING | Alternate session UID. |
| `uuid` | STRING | Session UUID. |

### Spark DDL

```sql
STRUCT<
  created_time: TIMESTAMP,
  credential_uid: STRING,
  expiration_reason: STRING,
  expiration_time: TIMESTAMP,
  is_mfa: BOOLEAN,
  is_remote: BOOLEAN,
  is_vpn: BOOLEAN,
  issuer: STRING,
  terminal: STRING,
  uid: STRING,
  uid_alt: STRING,
  uuid: STRING
>
```

### Where it’s used

- Top-level **`session`**: authentication, authorize_session.
- Nested in **actor.process.session** across account_change, api_activity, authentication, authorize_session, process_activity, file_activity, and others.

---

## user

**Type:** `STRUCT<...>`

User identity: name, type, UID, and MFA flag. Used as top-level **`user`** (e.g. authenticated user, user requesting authorization) and nested inside **actor** and **actor.process** as **user**.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `has_mfa` | BOOLEAN | Whether the user has MFA enabled. |
| `name` | STRING | Username or display name. |
| `type` | STRING | User type name (e.g. human, service). |
| `type_id` | INT | User type ID. |
| `uid` | STRING | User unique identifier. |

### Spark DDL

```sql
STRUCT<
  has_mfa: BOOLEAN,
  name: STRING,
  type: STRING,
  type_id: INT,
  uid: STRING
>
```

### Where it’s used

- Top-level **`user`**: authentication, authorize_session, account_change (user, user_result), group_management, and others.
- Nested in **actor.user** and **actor.process.user** across IAM and system activity tables.

---

## service

**Type:** `STRUCT<...>`

Service or application being authenticated to or authorized (e.g. AWS S3, Azure AD, Cisco IOS).

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | STRING | Service or application name. |
| `uid` | STRING | Service unique identifier. |

### Spark DDL

```sql
STRUCT<
  name: STRING,
  uid: STRING
>
```

### Where it’s used

- Top-level **`service`**: authentication, authorize_session.
