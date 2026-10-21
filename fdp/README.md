# FAIR Data Point (local deployment)

Set-up of the course guide (FAIR Data Point with GraphDB), with these changes:

- Image versions pinned: FDP 1.22.2, client 1.18.1, GraphDB 10.7.4, MongoDB 8.2.12. The guide's
  `mongo:4.0.12` cannot be used with FDP 1.22, whose driver needs MongoDB 4.2 or newer; 8.2.12 is
  the pairing in the FDP team's own compose files.
- FDP 1.22 requires a token-signing secret. Create `.env` next to `docker-compose.yml` with
  `FDP_JWT_SECRET_KEY=` followed by the output of `openssl rand -base64 48`.
- `application.yml` sets `persistentUrl` to `https://w3id.org/FAIR-course-UT/2026/group33/fdp`, so
  records are minted under the group's persistent namespace, and disables the ping to the public
  FDP index, because a local instance cannot be harvested.
- Ports are bound to 127.0.0.1; MongoDB is not published.

Start: create the GraphDB repository `fdp` and user `fdp` (guide steps 3 to 6, or the GraphDB REST
API), then `docker compose up -d`. Client: http://localhost:8085.
