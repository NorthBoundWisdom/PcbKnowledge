# Runtime secret mount point

Files in this directory are generated locally or provisioned by a secret manager and are ignored by Git. Run `../scripts/bootstrap-secrets.sh` from anywhere to create development values with owner-only permissions. The script also renders the Keycloak realm and confidential service client from committed secret-free templates; rendered JSON remains mode `0600` in this directory. `local_curator_password` is a random local-login credential, while `local_curator_marker` privately binds the automation-managed Keycloak identity; neither value is printed by Config or Build. The verifier database and object-store credentials are independent from the API, cleanup worker, and storage administrator. Do not add real values to this README, Compose, image layers, `.env`, logs, or test fixtures.

If an application or worker database credential may have been exposed, run
`../scripts/rotate-runtime-database-secrets.sh`. For a verifier credential, replace
`verifier_db_password` with a new owner-only random value. Then run the PostgreSQL role
reconciler and recreate the affected runtime containers. Object-store credential rotation
must also recreate SeaweedFS so its generated identity policy is refreshed.
