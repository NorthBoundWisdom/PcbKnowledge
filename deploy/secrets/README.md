# Runtime secret mount point

Files in this directory are generated locally or provisioned by a secret manager and are ignored by Git. Run `../scripts/bootstrap-secrets.sh` from anywhere to create development values with owner-only permissions. The script also renders the Keycloak realm and confidential service client from committed secret-free templates; rendered JSON remains mode `0600` in this directory. Do not add real values to this README, Compose, image layers, `.env`, logs, or test fixtures.

If an application or worker database credential may have been exposed, run
`../scripts/rotate-runtime-database-secrets.sh`, then run the PostgreSQL role
reconciler and recreate the API and worker containers.
