---
name: php-docker-upgrade
description: >
  Bump the PHP version of a Dockerized, Makefile-driven project (e.g. a Drupal
  site) to a target version — 8.4, 8.5 or later. Use when the user mentions
  upgrading PHP in Docker, changing the PHP base image / Dockerfile version,
  a "platform.php" constraint, or needs a newer PHP for a framework upgrade
  (e.g. PHP 8.4 required by Drupal 11). Covers locating the image, bumping it,
  rebuilding containers, verifying, and updating the Composer platform pin.
  IMPORTANT: all build commands MUST go through Makefile targets, never run
  directly on the host.
---

# PHP version upgrade in a Docker environment

Bump the PHP runtime of the containers to a **target version** BEFORE touching
the framework/core — otherwise `composer update` fails or the site won't boot.

**Target version is a parameter.** Set `<PHP_VERSION>` to what you need:

- Drupal 11 → **8.4** (current requirement)
- Future majors (e.g. Drupal 12) → **8.5+** — the procedure is identical, only
  the number changes.

If the caller (e.g. the `d11` orchestrator) already fixed the target, use it.
Otherwise run step 0 to decide whether a bump is needed, and to which version.

## 0. Check whether a bump is needed

Collect the five facts, then decide:

```bash
grep -rhoE 'FROM php:[0-9.]+[^ ]*' docker/                       # 1. current image
make composer c='show --self --format=json' | grep -A3 '"requires"' # 2a. the project's "php" constraint
grep -o '"php": *"[^"]*"' web/core/composer.json                  # 2b. the framework floor (Drupal core)
grep -nE '^image:|php-[0-9.]+' .gitlab-ci.yml                     # 4. the CI image
curl -s https://endoflife.date/api/php.json |                     # 3. support cycles
  python3 -c "import json,sys;[print(c['cycle'],'eol',c['eol'],'latest',c['latest']) for c in json.load(sys.stdin)[:5]]"
```

5. The **production runtime** (FPM, not only the CLI): ask the user, or read it
   from the deploy recipe (e.g. a pinned `bin/php`). Never SSH to find out.

| Situation | Decision |
|---|---|
| The current cycle is past `eol`, or below the framework floor | **Bump** to the newest cycle that the framework supports and production can run; production goes in the MR's prerequisites |
| The current cycle = production's, and a newer cycle is supported but production is still behind | **No bump.** Report the newer cycle as a follow-up: local must not run ahead of prod |
| Production / CI already moved to a newer cycle | **Bump** to match them |
| The current cycle = production = CI, and it is supported | **Nothing to do.** Say so, and still refresh the patch release: `make rebuild-no-cache` pulls the latest `x.y` image |

The framework's supported range comes from its docs (Drupal:
drupal.org/docs/getting-started/system-requirements/php-requirements), not from
the floor in `composer.json` alone. Report the five facts and the decision
before touching any file.

## Golden rule: everything goes through the Makefile

This project is **Dockerized and driven by a Makefile**. Never call `composer`,
`php` or `docker` directly on the host — use the `make` targets:

| Need | Make target |
|---|---|
| Rebuild images (with cache) | `make rebuild` |
| Rebuild without cache | `make rebuild-no-cache` |
| Shell in the PHP container | `make shell` |
| Composer install + npm install | `make install` |
| Generic Composer | `make composer <args>` |
| Drush status | `make drush c='status'` |

## 1. Locate the Dockerfile / PHP image

The image is defined either in a dedicated `Dockerfile` or in
`docker-compose.yml`.

```bash
grep -rn 'php:' docker/ 2>/dev/null
grep -rn 'FROM php' docker/ 2>/dev/null
find . -name 'Dockerfile*' -not -path './vendor/*' -not -path './node_modules/*'
```

## 2. Update the PHP version

In the PHP service Dockerfile, replace the base image version:

```dockerfile
# BEFORE
FROM php:8.3-fpm

# AFTER — <PHP_VERSION>, e.g. 8.4
FROM php:8.4-fpm
```

If the image comes from a tag in compose:

```yaml
# docker-compose.yml — php service
image: myregistry/php:8.4-fpm   # instead of 8.3
```

Verify the PHP extensions installed in the Dockerfile are compatible with the
target version (usually yes — double-check `pecl` / `docker-php-ext-*` calls).

## 3. Rebuild and restart

```bash
make rebuild                 # rebuild images and restart (with cache)
make rebuild-no-cache        # if the PHP layer doesn't refresh
```

## 4. Verify the new version

```bash
make shell
# inside the container:
php -v        # should display <PHP_VERSION>.x
exit

# or via drush
make drush c='status' | grep -i php
```

## 5. Reinstall dependencies under the new PHP

```bash
make install     # composer install + npm install
```

If Composer complains about a frozen `platform.php` constraint in
`composer.json`, update it to the target version:

```json
"config": {
    "platform": {
        "php": "8.4.0"
    }
}
```

then `make composer update --lock`.

## Where this fits in a framework upgrade

The PHP bump is a **technical prerequisite**, done first. For a full Drupal
10 → 11 upgrade it is step 2, followed by fixing deprecations and jQuery **while
still on D10**, then the core bump last — see the `d11` orchestrator skill.
