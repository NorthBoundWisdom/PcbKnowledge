# Configuration and secrets

Configuration is validated at process startup. There are no implicit production defaults for identity, database credentials, object-store credentials, allowed origins, or license policy.

## Local secret files

Compose mounts these untracked credential files as read-only Docker secrets:

| File | Consumer |
|---|---|
| `deploy/secrets/postgres_password` | PostgreSQL bootstrap administrator, migrations, runtime-role reconciliation |
| `deploy/secrets/application_db_password` | API and object-store initializer as the constrained `pcbknowledge_app` role |
| `deploy/secrets/worker_db_password` | Durable cleanup worker as the constrained `pcbknowledge_worker` role |
| `deploy/secrets/keycloak_db_password` | PostgreSQL bootstrap, Keycloak |
| `deploy/secrets/keycloak_admin_password` | Keycloak bootstrap administrator |
| `deploy/secrets/agent_service_client_secret` | Rendered confidential Keycloak service client and reconciliation |
| `deploy/secrets/seaweedfs_access_key` / `seaweedfs_secret_key` | SeaweedFS and API; permanent read plus staging read/write only |
| `deploy/secrets/seaweedfs_admin_access_key` / `seaweedfs_admin_secret_key` | SeaweedFS and the bounded bucket initializer only |
| `deploy/secrets/seaweedfs_worker_access_key` / `seaweedfs_worker_secret_key` | SeaweedFS and durable cleanup worker; staging bucket write/delete only |
| `deploy/secrets/grafana_admin_password` | Grafana |

`bootstrap-secrets.sh` creates the credential set above only when files do not
exist, refuses empty files, and enforces owner-only permissions. It also derives
`keycloak-realm.json` and `keycloak-agent-client.json` from committed templates;
both rendered files remain untracked and mode `0600`. Automation should verify
the required filenames rather than depend on a hard-coded total. The script does
not rotate secrets. Rotation must coordinate dependent services and verify
access before retiring the prior value.

## Non-secret development settings

Ports and image references can be overridden in the shell or an untracked `.env` file. See `deploy/.env.example`. Values prefixed with `VITE_` are public browser configuration and must never contain credentials.

Development image defaults use explicit release tags. Tags are mutable registry references and therefore not approved for production. Production deployment must override every `*_IMAGE` value with `repository@sha256:<digest>` and retain the resolved manifest as a release artifact.

## Production requirements

- Inject secrets from the deployment platform; do not copy development secret files into an image or Git.
- Use HTTPS and fixed public API/OIDC origins. Validate JWT signature, issuer, audience, expiry, and authorized scopes.
- Replace the development Keycloak realm with a reviewed realm export or external IdP integration. The browser client remains public and uses Authorization Code + PKCE; it has no client secret.
- Keep database, SeaweedFS, OTel, Prometheus, Grafana, and Keycloak management ports on private networks.
- Define CORS and trusted proxy settings explicitly.
- Export structured logs without tokens, source full text, project payloads, or model inputs.
- Qualify backup/restore and object digest checks before admitting permanent assets.

Any missing required value must stop the affected process. Do not add an anonymous, SQLite, in-memory, or known-credential fallback to make startup appear successful.
