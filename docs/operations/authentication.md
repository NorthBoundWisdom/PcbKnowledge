# M1 authentication operations

PcbKnowledge uses Keycloak as its reference identity provider. Curator Web and non-human agents are different OAuth clients and different subject kinds; one credential cannot silently cross that boundary.

## Client and token contract

| Client | Flow | Secret | Allowed realm roles | Required subject claim |
|---|---|---|---|---|
| `pcbknowledge-curator-web` | Authorization Code + PKCE S256 | none; public client | `DATA_CURATOR`, `DOMAIN_REVIEWER`, `KNOWLEDGE_ADMIN`, `AUDITOR` | `pcbknowledge_subject_kind=HUMAN` |
| `pcbknowledge-agent-service` | Client Credentials | runtime-generated | `AGENT_SERVICE` only | `pcbknowledge_subject_kind=SERVICE_ACCOUNT` |
| `pcbknowledge-api` | bearer-only audience | none | none | token `aud` contains `pcbknowledge-api` |

Keycloak adds the API audience and subject-kind claim with client-specific mappers. It also emits the standard `azp` claim. Both active clients have `fullScopeAllowed=false`; explicit role-scope mappings prevent the browser from receiving `AGENT_SERVICE` and prevent the service client from receiving human roles. Curator Web independently rejects service subject kind or `AGENT_SERVICE` if a realm is misconfigured.

Token roles never grant Curator Web capabilities. After OIDC validation, the browser calls the generated, Bearer-authenticated `GET /session` transport. Only its trusted database `external_subject` mapping, organization roles, and explicit project grants are converted to bounded UI capabilities. Project roles enable only project-scoped workspace operations; in particular, project-only `KNOWLEDGE_ADMIN` never grants organization-global `admin:operate`. Missing, denied, unavailable, malformed, service-kind, or roleless session projections clear the in-memory user and fail closed before a workspace route loads. The API remains the final authorization boundary for every operation and validates signature, issuer, audience, expiry, subject kind, organization/project scope, trusted role, and requested action.

## Human account status

The M1 reference stack configures the login protocol, but deliberately provisions no
human account or default password. The `pcbknowledge-admin` bootstrap identity belongs
to Keycloak's management realm and is not a Curator Web user. A usable human session
requires both an enabled user in the `pcbknowledge` realm and a matching trusted
`identity.external_subject` plus at least one organization or project membership in
PostgreSQL. Creating only one side fails closed. Human onboarding and its audited
administration workflow are not implemented in M1; do not work around that boundary by
using the Keycloak administrator or inserting an anonymous/default application user.

The local client registers exact callbacks for the normal Compose origin on port 8080,
the isolated FreeCM origin on port 18080, and the frontend development/test origins.
After any client-definition change, rerun FreeCM Config and Build so the input-bound
receipt and the existing Keycloak database are reconciled before Run.

## Browser storage policy

Access token, refresh token, and the OIDC `User` object are held by an `InMemoryWebStorage` user store. A reload therefore signs the browser out locally. They are never written to `localStorage` or `sessionStorage`.

Authorization redirects need a short-lived transaction record so the callback can recover the CSRF state and PKCE verifier after full-page navigation. Only that transaction record uses `sessionStorage`, under `pcbknowledge.oidc.transaction.*`, with a five-minute stale-state limit and startup cleanup. It must never contain an access token or refresh token. This distinction preserves functional PKCE without persisting the authenticated session.

## Callback logging boundary

Curator Web requests `response_mode=query`, so the one-time authorization code and state can appear in the callback query string. Caddy skips access logging for the callback and logout-callback paths before proxying, and the inner nginx exact-match locations also disable access logs. URL fragments are handled only by the browser and are not sent in HTTP requests, but the same callback paths remain excluded from both proxy logs. Provider error payloads are not reflected by the UI. Validate this invariant with:

```bash
./deploy/scripts/check-oidc-log-policy.sh
```

## Bootstrap and reconcile

Generate local secrets and rendered Keycloak imports:

```bash
./deploy/scripts/bootstrap-secrets.sh
```

The committed realm/client files contain placeholders only. The full bootstrap creates the required credential files described in [configuration](configuration.md); for identity it uses `agent_service_client_secret` to render `keycloak-realm.json` and `keycloak-agent-client.json` under ignored `deploy/secrets/`, with mode `0600`. It is idempotent: existing non-empty credentials are retained and the rendered files are refreshed from the current templates.

On an empty database, Keycloak imports the rendered realm. On an existing database, import does not overwrite the realm, so run the explicit idempotent reconciliation after Keycloak is healthy:

```bash
docker compose up --detach --wait postgres keycloak
docker compose run --rm keycloak-reconcile
```

Reconciliation also reapplies the realm-level login posture that a normal import cannot update on an existing volume: self-registration, password reset, and remember-me are disabled; brute-force protection is enabled; and `sslRequired=external`. The latter permits loopback/private-network HTTP for this local Compose topology while requiring reviewed TLS/proxy settings for external production traffic. It then creates missing fixed roles and clients, updates the public/confidential client safety settings and runtime secret, reapplies role scopes, and assigns only `AGENT_SERVICE` to the service account. It writes its temporary admin token only inside the short-lived container and truncates that file before exit. It never prints an access token or secret.

To prove an existing realm converges rather than merely checking committed JSON, run the live drift test against the local stack:

```bash
./deploy/keycloak/test-reconcile-realm.sh
```

The test deliberately enables insecure realm settings, verifies that the drift took effect, runs reconciliation, asserts the secure values, and repeats reconciliation plus assertion to prove idempotence. An exit trap reruns reconciliation if the test is interrupted after applying drift. Do not run it against a shared or production realm.

## Smoke verification

With Keycloak running and reconciled:

```bash
./deploy/keycloak/smoke-keycloak.sh
```

For the isolated FreeCM endpoints, exercise its exact callback with:

```bash
PCBKNOWLEDGE_KEYCLOAK_ISSUER_URL=http://localhost:18081/realms/pcbknowledge \
PCBKNOWLEDGE_CURATOR_REDIRECT_URI=http://localhost:18080/auth/callback \
./deploy/keycloak/smoke-keycloak.sh
```

The smoke check verifies discovery issuer, `code`, `S256`, and `client_credentials` metadata; sends a real browser authorization request with an S256 challenge; obtains a real client-credentials token without placing the secret on the command line; and checks only these decoded claims:

- `iss` equals the configured realm issuer;
- `aud` contains `pcbknowledge-api`;
- `azp` is `pcbknowledge-agent-service`;
- `pcbknowledge_subject_kind` is `SERVICE_ACCOUNT`;
- `realm_access.roles` is exactly `AGENT_SERVICE`.

The script prints only those safe fields. Token response, decoded payload, and newline-free secret copy stay in a mode-`0700` temporary directory and are deleted on exit. Do not enable shell tracing around this command.

## Production changes

- Replace `start-dev` and HTTP with reviewed TLS/hostname/proxy settings.
- Inject admin and service secrets from the deployment secret manager; rotate them with a coordinated reconcile and smoke receipt.
- Replace localhost redirect/origin values with exact HTTPS URLs. Never use wildcard production redirect URIs.
- Federate human identity as required, but do not assign `AGENT_SERVICE` to a human or a human role to the service account.
- Do not provision known demo users or passwords in the realm export.
