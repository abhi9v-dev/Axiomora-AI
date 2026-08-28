# infra

Local and deployment infrastructure configuration that isn't source code.

- `db/init.sql` — runs once when the Compose `db` service first initializes
  its data directory; enables the `vector` extension.

Production Docker images, deployment manifests and hosting configuration
(free-tier-compatible) are added in Phase 9.
