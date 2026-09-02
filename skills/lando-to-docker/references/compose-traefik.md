# `docker-compose.yml`, Traefik & local TLS

The compose file lives at `docker/compose/dev/docker-compose.yml` and is always
invoked with `--project-directory .` so relative paths and the root `.env`
resolve from the repo root (the Makefile does this).

## Prerequisite: a shared external Traefik + wildcard cert

All three projects route through **one shared Traefik instance** on an external
network — it is NOT defined per-project. Set it up once on the host:

```bash
# 1. Create the shared network (once per machine)
docker network create traefik-public

# 2. Trust a wildcard cert for *.dev.localhost (mkcert)
mkcert -install
mkcert "*.dev.localhost"           # feed the resulting cert/key to Traefik

# 3. Run a Traefik instance attached to traefik-public, exposing entrypoints
#    `web` (:80) and `websecure` (:443) with the mkcert cert as default.
```

`*.dev.localhost` resolves to `127.0.0.1` automatically (RFC 6761) — **no
`/etc/hosts` edits**. Traefik terminates TLS; app containers speak plain HTTP
internally and Drupal detects real HTTPS via `reverse_proxy` (see
`drupal-glue.md`). If the `traefik-public` network or the Traefik instance is
missing, `make up` fails to route.

## The compose file (single-site template)

`<project>` = `COMPOSE_PROJECT_NAME`. For the **multisite** apache router rule,
see the note at the end.

```yaml
services:
  apache:
    build:
      context: ../../apache
    depends_on:
      - php
    volumes:
      - ../../../:/var/www/html:ro          # code read-only for the web tier
    networks:
      - app-internal
      - traefik-public
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik-public"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}.rule=Host(`${COMPOSE_PROJECT_NAME}.dev.localhost`)"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}.entrypoints=web"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}.service=${COMPOSE_PROJECT_NAME}"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-secure.rule=Host(`${COMPOSE_PROJECT_NAME}.dev.localhost`)"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-secure.entrypoints=websecure"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-secure.tls=true"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-secure.service=${COMPOSE_PROJECT_NAME}"
      - "traefik.http.services.${COMPOSE_PROJECT_NAME}.loadbalancer.server.port=80"

  php:
    build:
      context: ../../../
      dockerfile: docker/php/Dockerfile
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ../../../:/var/www/html
      - ../../php/php.ini:/usr/local/etc/php/conf.d/99-custom.ini:ro
      - ../../php/xdebug.ini:/usr/local/etc/php/conf.d/docker-php-ext-xdebug.ini:ro
      - ../../php/www.conf:/usr/local/etc/php-fpm.d/zzz-custom.conf:ro
    working_dir: /var/www/html
    entrypoint: ["bash", "/var/www/html/docker/php/entrypoint.sh"]
    command: ["php-fpm"]
    environment:
      APP_ENV: ${APP_ENV}
      MYSQL_HOSTNAME: ${MYSQL_HOSTNAME:-db}
      MYSQL_PORT: ${MYSQL_PORT:-3306}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      MYSQL_PREFIX: ${MYSQL_PREFIX}
      REDIS_HOSTNAME: ${REDIS_HOSTNAME:-redis}
      REDIS_PORT: ${REDIS_PORT:-6379}
      REDIS_PASSWORD: ${REDIS_PASSWORD}
      HASH_SALT: ${HASH_SALT}
      TRUSTED_HOST_PATTERNS: ${TRUSTED_HOST_PATTERNS}
      HOME_URL: https://${COMPOSE_PROJECT_NAME}.dev.localhost
      THEME_FOLDER: ${THEME_FOLDER}
      SMTP_HOSTNAME: ${SMTP_HOSTNAME:-mailpit}
      SMTP_PORT: ${SMTP_PORT:-1025}
      SMTP_EMAIL_FROM: ${SMTP_EMAIL_FROM}
      XDEBUG_MODE: ${XDEBUG_MODE:-off}
      USER_ID: ${USER_ID:-1000}
      GROUP_ID: ${GROUP_ID:-1000}
    networks:
      - app-internal

  db:
    image: mariadb:11.8
    environment:
      MARIADB_DATABASE: ${MYSQL_DATABASE}
      MARIADB_USER: ${MYSQL_USER}
      MARIADB_PASSWORD: ${MYSQL_PASSWORD}
      MARIADB_RANDOM_ROOT_PASSWORD: "yes"
    volumes:
      - db-data:/var/lib/mysql
      # multisite only — provision one DB/user per site (see drupal-glue.md):
      # - ../../mariadb/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      timeout: 5s
      retries: 20
    networks:
      app-internal:
        aliases:
          - ${COMPOSE_PROJECT_NAME}     # lets settings.php use host=<project> if desired

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20
    networks:
      - app-internal

  node:
    build:
      context: ../../node
    working_dir: /var/www/html
    command: ["tail", "-f", "/dev/null"]     # idle; commands run via `make npm-*`
    volumes:
      - ../../../:/var/www/html
    ports:
      - "${VITE_SERVER_PORT:-3000}:${VITE_SERVER_PORT:-3000}"
    environment:
      THEME_FOLDER: ${THEME_FOLDER}
    networks:
      - app-internal
      - traefik-public
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik-public"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-vite.rule=Host(`${COMPOSE_PROJECT_NAME}-vite.dev.localhost`)"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-vite.entrypoints=websecure"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-vite.tls=true"
      - "traefik.http.services.${COMPOSE_PROJECT_NAME}-vite.loadbalancer.server.port=${VITE_SERVER_PORT:-3000}"

  adminer:
    image: adminer:5.4.2
    depends_on:
      - db
    environment:
      ADMINER_DEFAULT_SERVER: db
      ADMINER_DESIGN: dracula
    networks:
      - app-internal
      - traefik-public
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik-public"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-adminer.rule=Host(`${COMPOSE_PROJECT_NAME}-adminer.dev.localhost`)"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-adminer.entrypoints=websecure"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-adminer.tls=true"
      - "traefik.http.services.${COMPOSE_PROJECT_NAME}-adminer.loadbalancer.server.port=8080"

  mailpit:
    image: axllent/mailpit:v1.29.6
    networks:
      - app-internal
      - traefik-public
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik-public"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-mailpit.rule=Host(`${COMPOSE_PROJECT_NAME}-mailpit.dev.localhost`)"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-mailpit.entrypoints=websecure"
      - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-mailpit.tls=true"
      - "traefik.http.services.${COMPOSE_PROJECT_NAME}-mailpit.loadbalancer.server.port=8025"

volumes:
  db-data:
    name: ${COMPOSE_PROJECT_NAME}-db-data
  redis-data:
    name: ${COMPOSE_PROJECT_NAME}-redis-data

networks:
  app-internal:
    name: ${COMPOSE_PROJECT_NAME}-internal
    driver: bridge
  traefik-public:
    external: true
```

## Service map (Lando → Docker)

| Lando | Docker replacement | Image |
|---|---|---|
| `appserver` (via: apache) | split **apache** proxy + **php** fpm | `httpd:2.4-alpine` + `php:8.4-fpm` |
| `database` (mariadb/mysql) | **db** | `mariadb:11.8` |
| `redis` | **redis** | `redis:7-alpine` |
| `node` | **node** | `node:22-alpine` |
| `mailhog` | **mailpit** | `axllent/mailpit:v1.29.6` |
| `pma` (phpMyAdmin) | **adminer** | `adminer:5.4.2` |
| `elasticsearch` | **dropped** — not carried over (projects use `search_api_db`) | — |
| `proxy: *.lndo.site` | Traefik labels → `*.dev.localhost` | shared external Traefik |
| `tooling:` block | the **Makefile** | see `makefile.md` |

Only the node dev-server port is published to the host; php:9000 and the DB port
stay internal. The web tier mounts code **read-only**; php and node mount it
read-write.

## Multisite apache router rule

For a multisite install, the apache router must match every site hostname. Use a
Traefik OR-rule and map hostnames in `web/sites/sites.php` (see `drupal-glue.md`):

```yaml
- "traefik.http.routers.${COMPOSE_PROJECT_NAME}-secure.rule=Host(`site_a.dev.localhost`) || Host(`site_b.dev.localhost`) || Host(`site_c.dev.localhost`)"
```

and give the `db` service one network alias per site id so `host => <site_id>`
resolves to the single shared MariaDB:

```yaml
  db:
    networks:
      app-internal:
        aliases:
          - site_a
          - site_b
          - site_c
```
