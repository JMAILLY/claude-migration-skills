# The `Makefile` — the deliverable that replaces `lando <cmd>`

The Makefile is the single developer entrypoint after the migration; every
`drush`/`composer`/`npm` call is wrapped so **nothing runs on the host**. This is
the artifact all the other skills (`d11`, `gulp-to-vite`, `sass-migrator`,
`php-docker-upgrade`) depend on.

## Header wiring

```make
COMPOSE ?= docker compose
DC       = $(COMPOSE) --project-directory . -f docker/compose/dev/docker-compose.yml
PHP       = php
NODE_SVC  = node
SITE     ?= default                        # multisite: default site id, override `make cr SITE=site_b`
EXEC_PHP  = $(DC) exec --user www-data $(PHP)
EXEC_NODE = $(DC) exec $(NODE_SVC)
COMPOSER  = $(EXEC_PHP) composer
DRUSH     = $(EXEC_PHP) vendor/bin/drush --uri=$(SITE)

COMPOSE_PROJECT_NAME := $(shell grep -E '^COMPOSE_PROJECT_NAME=' .env | cut -d= -f2)

# Positional argument capture (see "Argument passing" below)
ARG  := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
FILE := $(word 2,$(MAKECMDGOALS))

.DEFAULT_GOAL := help
```

- `--project-directory .` makes the root `.env` and relative build contexts
  resolve from the repo root even though the compose file is nested.
- **PHP/drush/composer run as `--user www-data`** (remapped to the host UID/GID
  at entrypoint); node runs as the default user.

## Argument passing (two styles)

1. **Named variable** — `make drush c='cr'`, `make npm c='install'`,
   `make uli uid=1`, `make en m=devel`.
2. **Positional passthrough** — `make en devel admin_toolbar`,
   `make composer-require drupal/foo`, `make db-import dump.sql`. This relies on
   `ARG`/`FILE` above plus a **catch-all no-op rule** so Make doesn't error on
   the extra words treated as goals:

```make
# Swallow extra positional words so they aren't run as targets
%:
	@:
```

Targets combine both with `$(or $(ARG),$(c))` / `$(or $(ARG),$(m))`.

## Targets

```make
## up: Start containers and print URLs
up:
	$(DC) up -d
	@echo "Site:    https://$(COMPOSE_PROJECT_NAME).dev.localhost"
	@echo "Adminer: https://$(COMPOSE_PROJECT_NAME)-adminer.dev.localhost"
	@echo "Mailpit: https://$(COMPOSE_PROJECT_NAME)-mailpit.dev.localhost"
	@echo "Vite:    https://$(COMPOSE_PROJECT_NAME)-vite.dev.localhost"

## down: Stop containers
down:
	$(DC) down

## restart: Restart containers
restart:
	$(DC) restart

## rebuild: Rebuild images and restart
rebuild:
	$(DC) down
	$(DC) build
	$(MAKE) up

## rebuild-no-cache: Rebuild images from scratch
rebuild-no-cache:
	$(DC) down
	$(DC) build --no-cache
	$(MAKE) up

## destroy: Stop and REMOVE volumes (drops DB + Redis data)
destroy:
	$(DC) down -v --remove-orphans

## logs: Follow php logs
logs:
	$(DC) logs -f php

## shell: Open a bash shell in the php container
shell:
	$(DC) exec php bash

## install: composer install + npm install
install:
	$(COMPOSER) install
	$(EXEC_NODE) npm install

## init: First-run bootstrap (.env, HASH_SALT, build, up)
init:
	@test -f .env || cp .env.example .env
	@# Generate HASH_SALT (OS-aware sed)
	@salt=$$(openssl rand -base64 55 | tr -d '\n/'); \
	if [ "$$(uname)" = "Darwin" ]; then \
		sed -i '' "s|^HASH_SALT=.*|HASH_SALT='$$salt'|" .env; \
	else \
		sed -i "s|^HASH_SALT=.*|HASH_SALT='$$salt'|" .env; \
	fi
	$(DC) up -d --build --wait
	$(COMPOSER) install
	$(EXEC_PHP) mkdir -p storage/private/default/logs
	$(EXEC_NODE) npm install
	$(EXEC_NODE) npm run build
	$(MAKE) up
	@echo "Now: make db-import <dump>  &&  make cim  &&  make cr"

## drush: Run a drush command — make drush c='cr'
drush:
	$(DRUSH) $(c)

## cr: Rebuild caches
cr:
	$(DRUSH) cr

## cex: Export config
cex:
	$(DRUSH) cex --yes

## cim: Import config then rebuild caches
cim:
	$(DRUSH) cim --yes
	$(DRUSH) cr

## updb: Run database updates
updb:
	$(DRUSH) updb --yes

## uli: One-time login link — make uli uid=1
uli:
	$(DRUSH) user:login --uid=$(or $(uid),1)

## en: Enable module(s) — make en devel admin_toolbar
en:
	$(DRUSH) en $(or $(ARG),$(m))

## pmu: Uninstall module(s) — make pmu devel
pmu:
	$(DRUSH) pmu $(or $(ARG),$(m))

## site-install: Install from existing config
site-install:
	$(DRUSH) site:install --existing-config --yes

## translate: Refresh translations
translate:
	$(DRUSH) locale:check
	$(DRUSH) locale:update
	$(DRUSH) cr

## composer: Run composer — make composer update
composer:
	$(COMPOSER) $(or $(ARG),$(c))

## composer-require: Require a package — make composer-require drupal/foo
composer-require:
	$(COMPOSER) require $(or $(ARG),$(m))

## composer-remove: Remove a package
composer-remove:
	$(COMPOSER) remove $(or $(ARG),$(m))

## db-export: Dump the DB (gzipped) into _dumps/
db-export:
	@mkdir -p _dumps
	$(DRUSH) sql-dump --gzip > _dumps/dump-$$(date +%Y%m%d-%H%M%S).sql.gz

## db-import: Import a dump — make db-import _dumps/dump.sql[.gz]
db-import:
	@test -n "$(FILE)" || { echo "Usage: make db-import <file>"; exit 1; }
	$(DRUSH) sql-drop --yes
	@case "$(FILE)" in \
	  *.gz) gunzip -c "$(FILE)" | $(DC) exec -T --user www-data $(PHP) vendor/bin/drush --uri=$(SITE) sql-cli ;; \
	  *)    $(DC) exec -T --user www-data $(PHP) vendor/bin/drush --uri=$(SITE) sql-cli < "$(FILE)" ;; \
	esac
	$(DRUSH) cr

## npm: Run npm in the node container — make npm c='install'
npm:
	$(EXEC_NODE) npm $(c)

## npm-install: Install node deps (root + theme if applicable)
npm-install:
	$(EXEC_NODE) npm install

## npm-dev: Vite/Gulp dev server (HMR)
npm-dev:
	$(EXEC_NODE) npm run dev

## npm-build: Build frontend assets
npm-build:
	$(EXEC_NODE) npm run build

## phpcs / phpcbf / phpstan / prettier: Quality tools
phpcs:
	$(EXEC_PHP) vendor/bin/phpcs
phpcbf:
	$(EXEC_PHP) vendor/bin/phpcbf
phpstan:
	$(EXEC_PHP) vendor/bin/phpstan
prettier:
	$(EXEC_NODE) npm run prettier

## help: Show this help
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //' | awk -F': ' '{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# Catch-all: swallow positional args so they aren't treated as targets
%:
	@:
```

> `db-import` uses `exec -T` (no TTY) because it pipes stdin. `destroy` drops the
> DB volume — needed to re-run the multisite init SQL (it only runs on an empty
> data volume).

## Multisite additions

```make
SITES = site_a site_b site_c

## cr-all: Rebuild caches for every site
cr-all:
	@for s in $(SITES); do echo "== $$s =="; $(EXEC_PHP) vendor/bin/drush --uri=$$s cr; done
```

`make cr SITE=site_b` targets one site; `make cr-all` loops them all.

## Coverage check vs the old `tooling:` block

Every `lando <cmd>` must have a target: `drush`→`make drush`, `composer`→
`make composer`, `npm`/`node`/`yarn`→`make npm`, `gulp`→`make npm-dev`/`npm-build`.
Lando `xdebug-on`/`xdebug-off` → the `XDEBUG_MODE` env var (no target needed).
