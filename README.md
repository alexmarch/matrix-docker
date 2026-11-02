# Matrix: Synapse + Element

Docker Compose infrastructure for a public Matrix homeserver with PostgreSQL,
Element Web, Synapse Admin, HTTPS, and TURN for 1:1 audio/video calls.

## Requirements

- A Linux server with Docker Engine and the Docker Compose plugin.
- DNS A records for `matrix`, `chat`, `admin`, and `turn` hostnames pointing to
  the server's public IPv4 address.
- Inbound TCP ports `80`, `443`, and `3478`; UDP ports `3478`, `443`, and
  `49160-49200`. The firewall/security group must allow them too.
- An available Docker subnet `172.29.0.0/16`; change the network and coturn's
  private relay address together if it conflicts with the host network.

The homeserver name is permanent for Matrix user IDs. Choose it before the
first start: users will look like `@alice:matrix.example.com`.

## First start

1. Copy `.env.example` to `.env`. Replace all example hostnames/IPs and generate
   three independent secrets:

   ```sh
   cp .env.example .env
   openssl rand -hex 32
   ```

   Put separate generated values in `POSTGRES_PASSWORD`,
   `TURN_SHARED_SECRET`, and `REGISTRATION_SHARED_SECRET`. `TURN_PUBLIC_IP`
   must be the server's publicly reachable IPv4 address, not its Docker or
   private LAN address. If the server is behind NAT, use the router's public IP
   and forward the listed TURN ports to the server.

2. Generate Synapse's initial config and signing key, then render the
   environment-specific settings:

   ```sh
   docker compose run --rm synapse-generate
   docker compose run --rm config-render
   ```

   Rerun `config-render` after changing `.env`. It updates Synapse settings in
   the generated config and regenerates Element/coturn config files.

3. Start the services:

   ```sh
   docker compose up -d
   docker compose logs -f synapse caddy coturn
   ```

   Caddy obtains and renews HTTPS certificates automatically. The configured
   hostnames must resolve publicly before startup.

If `config-render` reports that `TURN_PUBLIC_IP` is not public, replace its
value in `.env` with the public IPv4 address assigned to the server (the
`.env.example` value is only a placeholder). A private address such as
`10.x.x.x`, `172.16-31.x.x`, or `192.168.x.x` cannot be used there.

## Create the first admin and accounts

Create the first administrator interactively:

```sh
docker compose exec synapse \
  register_new_matrix_user http://localhost:8008 \
  -c /data/homeserver.yaml --admin
```

Sign in to `https://admin.example.com` with this account. Synapse Admin lets
administrators create and manage multiple Matrix accounts. Keep public
registration disabled; create subsequent users from the admin UI.

After creating the first admin, remove `registration_shared_secret` from
`homeserver.yaml` and restart Synapse:

```sh
docker compose exec synapse sh -c \
  "sed -i '/^registration_shared_secret:/d' /data/homeserver.yaml"
docker compose restart synapse
```

The shared secret is only needed for initial CLI registration. Do not expose
the `.env` file or generated Synapse config.

## Endpoints and operations

- Client and federation API: `https://matrix.example.com`
- Element Web: `https://chat.example.com`
- Admin UI: `https://admin.example.com`
- TURN: `turn.example.com:3478`

Replace the example hostnames in this list with the values from `.env`.

Back up the `postgres_data` and `synapse_data` volumes. Caddy's
`caddy_data` volume contains certificates and should also be preserved.
Synapse and frontend images use moving tags; for production, pin tested image
versions and update them deliberately.
