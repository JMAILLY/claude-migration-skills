# Image versions: resolve, don't copy

The tags in the other references are a baseline from when they were written,
not a target. Resolve every image at migration time and report it.

## Sources

```bash
# Tags of a Docker Hub image, newest last (repo = library/<name> for official images).
tags() { curl -s "https://hub.docker.com/v2/repositories/$1/tags?page_size=100&ordering=last_updated" |
  python3 -c "import json,sys,re;t=[x['name'] for x in json.load(sys.stdin)['results']];k=lambda s:[int(n) for n in re.findall(r'\d+',s)];print(sorted([x for x in t if re.fullmatch(r'v?\d+(\.\d+)*(-$2)?',x)],key=k)[-5:])"; }
tags library/adminer ''; tags axllent/mailpit ''; tags library/redis alpine; tags library/httpd alpine

# Support cycles: LTS flag, end of life, latest patch.
cycles() { curl -s "https://endoflife.date/api/$1.json" |
  python3 -c "import json,sys;[print(c['cycle'],'lts',c.get('lts'),'eol',c.get('eol'),'latest',c.get('latest')) for c in json.load(sys.stdin)[:5]]"; }
cycles php; cycles nodejs; cycles mariadb; cycles redis
```

`php` has hundreds of tags, so the Docker Hub listing is useless for it. Take the
cycle from endoflife.date and use `php:<major.minor>-fpm`.

## Rule per image

| Image | Pick | Pin as |
|---|---|---|
| `adminer`, `axllent/mailpit` (dev-only tools) | newest release | exact tag (`adminer:6.1.2`, `axllent/mailpit:v1.31.6`): reproducible, and bumped on purpose |
| `httpd` | newest `2.4` line | `httpd:2.4-alpine` |
| `redis` | newest major | `redis:<major>-alpine` |
| `php` | newest cycle the framework supports **and** the production runtime runs | `php:<x.y>-fpm` |
| `node` | newest **LTS** (`lts` is a date in the past) that the CI image also runs (it builds the assets in production) | `node:<major>-alpine` |
| `mariadb` / `mysql` | newest **LTS** not newer than production's server | `mariadb:<x.y>` |

Runtimes follow production on purpose. A local PHP or DB ahead of prod lets code
pass locally and fail on deploy (a PHP 8.5-only syntax, a MariaDB-only SQL
function). When a newer supported version exists, the image stays on the prod
version, and the newer version goes in the report as a follow-up (PHP:
`php-docker-upgrade`). Ask the user for the prod versions. Do not SSH to find
out.

Non-LTS short-term releases (MariaDB `x.0`–`x.2`, odd Node majors) are never the
target, even when they are the newest tag.

## After a bump

- `make rebuild-no-cache && make up`, then the Step 6 checks.
- A major bump of a tool (Adminer 5 → 6, Redis 7 → 8) can change the
  environment variables or the default port. Re-read the image's docs, and open
  Adminer and Mailpit once.
- The DB image only changes the server binary: the named volume keeps its data.
  The MariaDB image upgrades the data dir only when `MARIADB_AUTO_UPGRADE=1` is
  set, so set it or `make db-import` again.

## Report (MR body and final summary)

| Image | File | Status | Newer version |
|---|---|---|---|
| `httpd:2.4-alpine` | `docker/apache/Dockerfile` | supported | — |
| `mariadb:11.8` | `docker/compose/dev/docker-compose.yml` | LTS, = prod | 12.3 (LTS), held back: prod is on 11.8 |
| `adminer:6.1.2` | `docker/compose/dev/docker-compose.yml` | bumped from 5.4.2 | — |
| `node:24-alpine` | `docker/node/Dockerfile` | Active LTS, bumped from 22 | — (26 becomes LTS on its `lts` date) |
| `php:8.4-fpm` | `docker/php/Dockerfile` | supported, = prod | 8.5, held back: prod on 8.4 |

"Status" holds the support state (endoflife.date) plus why the version was kept.
"Newer version" is empty only when nothing newer and usable exists.
