---
name: lando-to-docker
description: >
  Migrate a Drupal project's local dev environment from Lando to Docker Compose
  + a Makefile (Traefik reverse proxy, *.dev.localhost, PHP-FPM + Apache, MariaDB,
  Redis, Adminer, Mailpit). Use when the user mentions replacing Lando, a
  ".lando.yml", "lando to docker", "lando to make", setting up the Makefile /
  Docker dev environment, or needs the Makefile that the d11 / gulp-to-vite /
  sass-migrator / php-docker-upgrade skills require. Produces the docker/ tree,
  docker-compose.yml, Makefile, and Drupal glue; handles single-site vs
  multisite and Gulp vs Vite/Tailwind frontends. IMPORTANT: after migration all
  commands MUST go through Makefile targets, never Lando or the host.
---

# Lando → Docker Compose + Makefile (Drupal local dev)

This is the **upstream prerequisite** skill: it produces the `Makefile` (and the
Dockerized environment behind it) that `d11`, `gulp-to-vite`, `sass-migrator`
and `php-docker-upgrade` all depend on. The target architecture is the one used
across the reference projects (ginger-cebtp, sterimed, akena):

```
Traefik (shared, external)  ──►  apache (httpd:2.4-alpine, proxy_fcgi)
  *.dev.localhost, TLS            └─►  php (php:8.4-fpm)
                                        ├─ db      (mariadb:11.8)
                                        ├─ redis   (redis:7-alpine)
                                        ├─ node    (node:22-alpine, idle)
                                        ├─ adminer (adminer:5.4.2)
                                        └─ mailpit (axllent/mailpit)
```

## Golden rule

The **Makefile is the single developer entrypoint** — after this migration,
every `drush`/`composer`/`npm` runs through a `make` target inside a container,
never via `lando` and never on the host. Building that Makefile faithfully is
the core deliverable.

## Prerequisites (host, once per machine)

A **shared external Traefik** and a local wildcard cert — see
`references/compose-traefik.md`:

```bash
docker network create traefik-public
mkcert -install && mkcert "*.dev.localhost"     # feed cert to the Traefik instance
```

`*.dev.localhost` resolves to 127.0.0.1 automatically — no `/etc/hosts` edits.
If the user has no shared Traefik, say so and point them at the reference before
generating the stack (the stack assumes it exists).

## Step 0 — Inventory the `.lando.yml` and decide the variants

Read `.lando.yml` (and `.lando.local.yml` if present; recover from git history
if already deleted). Extract: recipe, PHP version, web server, DB type+version,
node version, extra services (redis, search, cache), the `tooling:` commands,
and the `proxy:` hostnames. Then settle the three decisions that shape the
output:

| Decision | Detect | Effect |
|---|---|---|
| **Single-site vs multisite** | multiple `proxy` hostnames / per-site DB services / `web/sites/sites.php` | multisite adds `sites.php`, per-site init SQL + DB network aliases, per-site env prefix, `SITES` loop → `references/drupal-glue.md` |
| **Frontend build** | `gulpfile.js` vs `vite.config.*` vs Tailwind (`@tailwindcss/*`) | node image toolchain + HMR wiring → `references/frontend-build.md` |
| **Extra services** | `elasticsearch`, other | usually **dropped** (projects use `search_api_db`); only keep ES if a `search_api_elasticsearch` backend is really configured |

> Capture the target `COMPOSE_PROJECT_NAME` (the base hostname) and the theme
> folder now — they thread through every file.

## Step 1 — Create the `docker/` tree

Create the image/config files verbatim from **`references/docker-images.md`**:
`docker/php/{Dockerfile,entrypoint.sh,php.ini,www.conf,xdebug.ini}`,
`docker/apache/{Dockerfile,vhost.conf}`, `docker/node/Dockerfile`, and
`.dockerignore`. Pick the node Dockerfile form based on the frontend decision
(toolchain only if `imagemin`/`optipng` is a dependency).

> Do not skip `www.conf` (`clear_env = no`) — it is load-bearing: without it the
> env-driven DB/Redis/SMTP config in `settings.php` is silently empty. Which of
> `$_ENV` / `getenv()` actually holds the values also depends on the project's
> `.env` loader — see "Which source holds the `.env` values" in drupal-glue.md
> before writing any env-driven condition.

## Step 2 — Write `docker/compose/dev/docker-compose.yml`

From **`references/compose-traefik.md`**: all services, the Traefik label
pattern (web + websecure routers, `tls=true`), the `app-internal` bridge and the
`traefik-public` external network, named volumes. For multisite, apply the
apache OR-rule and the per-site `db` network aliases.

## Step 3 — Write the `Makefile`

From **`references/makefile.md`**: the header wiring, the dual argument-passing
convention (named `c=`/`m=`/`uid=` **and** positional with the catch-all `%:`
rule), and every target. **Verify coverage**: each `lando <cmd>` from the old
`tooling:` block must map to a target (`drush`→`make drush`, `composer`→
`make composer`, `npm/node/yarn`→`make npm`, `gulp`→`make npm-dev`/`npm-build`).
Add the `SITES` loop + `cr-all` for multisite.

## Step 4 — Drupal glue

From **`references/drupal-glue.md`**: point the DB `host` at the compose service
(`db`) or network alias, read creds from `$_ENV`, set `config_sync_directory`,
`trusted_host_patterns`, the **`reverse_proxy` block** (Traefik terminates TLS),
and the empty-password Redis guard. Update drush aliases (`/app` →
`/var/www/html`, `*.lndo.site` → `https://*.dev.localhost`). For multisite, add
`web/sites/sites.php`, the per-site init SQL, and the per-site `$_ENV` prefix
logic.

> `web/sites/*/settings.php` is often git-ignored (a local file) — edit wherever
> the project actually reads DB config (a tracked `base.settings.php`, a
> `settings.local.php`, or the developer's local `settings.php`).

## Step 5 — `.env.example` + bring it up

Write `.env.example` (see `references/drupal-glue.md`), then:

```bash
cp .env.example .env      # or: make init (generates HASH_SALT, builds, boots)
# set USER_ID / GROUP_ID from `id -u` / `id -g`
make init                 # first run: .env, HASH_SALT, build, up
make db-import _dumps/<dump>.sql.gz
make cim
make cr
```

## Step 6 — Verify

```bash
make up                                    # prints the URLs
make drush c='status'                      # DB connected, bootstrap OK, shows PHP version
curl -ksI https://<project>.dev.localhost | head -1   # 200/301 via Traefik
make npm-build                             # frontend builds in the node container
```

Manual checks:

- [ ] `https://<project>.dev.localhost` loads (TLS via Traefik, no cert warning)
- [ ] Adminer at `https://<project>-adminer.dev.localhost`, Mailpit at `-mailpit`
- [ ] `make uli uid=1` logs in
- [ ] Edits to files on the host are picked up (bind mount + UID/GID remap OK)
- [ ] `make npm-dev` HMR works (Vite/Gulp) if applicable
- [ ] (multisite) each site resolves and reaches its own DB

## Hand-off to the other skills

Once `make drush c='status'` is green, the Makefile contract the other skills
rely on exists. Natural next steps: **`php-docker-upgrade`** (bump PHP),
**`d11`** (Drupal 10 → 11), **`gulp-to-vite`**, **`sass-migrator`**.

## Git workflow

One focused branch + a single MR is enough (this is one coherent change). If the
`gm:merge-request` skill is available, delegate the branch/commit/MR to it;
otherwise do a plain branch → commit → push (open the MR with `glab` if
authenticated), or commit on the current branch — ask the user which. Keep the
old `.lando.yml` deletion in the same commit as the new `docker/` + `Makefile`.

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `make up` fails / nothing routes | `traefik-public` network or Traefik instance missing | Create the network + run Traefik (Prerequisites) |
| Cert warning on `*.dev.localhost` | mkcert root not installed / cert not loaded into Traefik | `mkcert -install`; feed `*.dev.localhost` cert to Traefik |
| Site can't connect to DB, `$_ENV` empty | `clear_env = no` missing from `www.conf` | Add it, `make rebuild` |
| `getenv('APP_ENV')` is `FALSE` while `$_ENV['APP_ENV']` is set | `vlucas/phpdotenv` populates only the superglobals | Read `$_ENV`, or move `load.environment.php` to `symfony/dotenv` + `usePutenv(TRUE)` (drupal-glue.md) |
| Dev-only settings apply on prod/CI | an `$_ENV['APP_ENV'] ?? 'local'` fallback — fail-open | Strict `=== 'local'`, no fallback (drupal-glue.md) |
| Redis `ERR AUTH ... without any password` | empty-string password sent as a real password | `!empty()` guard → NULL (see drupal-glue.md) |
| Redirect loops / wrong-scheme URLs | `reverse_proxy` not set; Traefik TLS not trusted | Add the `reverse_proxy` block to settings |
| Root-owned files on host / permission errors | `USER_ID`/`GROUP_ID` not set to host values | Set from `id -u`/`id -g`, `make rebuild` |
| `npm install` fails on Apple Silicon | `imagemin-optipng` native build | Toolchain node Dockerfile form (docker-images.md) |
| Vite HMR dead / mixed-content | `wss`/`clientPort`/CSP/library scheme mismatch | HMR checklist in frontend-build.md |
| Multisite init SQL didn't run | init SQL only runs on an empty volume | `make destroy` then `make init` |
| `updb`/`cr` order errors after a later core bump | unrelated — that's the `d11` skill | see `d11` |

## Reference files

- `references/docker-images.md` — verbatim `docker/` Dockerfiles + config
- `references/compose-traefik.md` — `docker-compose.yml`, Traefik labels, mkcert
- `references/makefile.md` — full Makefile template + argument passing
- `references/drupal-glue.md` — settings/sites/drush/.env, single vs multisite
- `references/frontend-build.md` — node image toolchain + Gulp/Vite/Tailwind HMR
