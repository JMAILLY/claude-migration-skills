# The `docker/` tree — verbatim image & config templates

These files are **identical across the reference projects** (ginger-cebtp,
sterimed, akena). Copy them as-is; the only per-project variation is the
frontend `node` image (see `frontend-build.md`). Replace `<project>` with the
`COMPOSE_PROJECT_NAME` and `<theme>` with the custom theme folder where noted.

Layout:

```
docker/
├── apache/
│   ├── Dockerfile
│   └── vhost.conf
├── php/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── php.ini
│   ├── www.conf
│   └── xdebug.ini
├── node/
│   └── Dockerfile
├── mariadb/
│   └── init/            # multisite only — see drupal-glue.md
└── compose/
    └── dev/
        └── docker-compose.yml   # see compose-traefik.md
```

---

## `docker/php/Dockerfile` — PHP-FPM application container

```dockerfile
FROM php:8.4-fpm
LABEL description="Drupal development environment"

# mlocati's extension installer — resolves system deps automatically
ADD --chmod=0755 https://github.com/mlocati/docker-php-extension-installer/releases/latest/download/install-php-extensions /usr/local/bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential imagemagick default-mysql-client git openssh-client \
    curl nano rsync gnupg zip unzip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN install-php-extensions \
    pdo_mysql gd opcache zip intl redis xdebug imagick

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html
RUN chown -R www-data:www-data /var/www
EXPOSE 9000
CMD ["php-fpm"]
```

> Set the PHP version to the site's requirement (8.4 for Drupal 11). For a later
> D11→D12 upgrade this is what the `php-docker-upgrade` skill bumps.

## `docker/php/entrypoint.sh` — UID/GID remap + storage prep + DB wait

```bash
#!/bin/bash
set -e
umask 0002
echo "=== Starting Drupal Development Container ==="

# Remap www-data to the host user at RUNTIME so bind-mounted files stay
# editable on the host and writable in the container.
if [ -n "${USER_ID}" ] && [ "${USER_ID}" != "0" ]; then
    usermod --non-unique --uid "${USER_ID}" www-data
fi
if [ -n "${GROUP_ID}" ] && [ "${GROUP_ID}" != "0" ]; then
    groupmod --non-unique --gid "${GROUP_ID}" www-data
fi

# Create Drupal storage directories
mkdir -p /var/www/html/storage/private/default
mkdir -p /var/www/html/storage/tmp/default
mkdir -p /var/www/html/web/sites/default/files
mkdir -p /var/log/php
chown -R www-data:www-data /var/www/html/storage /var/www/html/web/sites/default/files /var/log/php
chmod -R 775 /var/www/html/storage /var/www/html/web/sites/default/files

# Wait for the database (30 tries, 2s apart)
if [ -n "$MYSQL_HOSTNAME" ]; then
    tries=0
    until php -r "new PDO('mysql:host=${MYSQL_HOSTNAME};port=${MYSQL_PORT:-3306}', '${MYSQL_USER}', '${MYSQL_PASSWORD}');" 2>/dev/null; do
        tries=$((tries+1))
        [ "$tries" -ge 30 ] && echo "DB not reachable, continuing anyway" && break
        echo "Waiting for database... ($tries/30)"
        sleep 2
    done
fi

echo "=== Development Container Ready ==="
exec "$@"
```

Referenced in compose as `entrypoint: ["bash", "/var/www/html/docker/php/entrypoint.sh"]` + `command: ["php-fpm"]`.

## `docker/php/php.ini` → mounted at `/usr/local/etc/php/conf.d/99-custom.ini`

```ini
error_reporting = E_ALL & ~E_NOTICE & ~E_WARNING & ~E_DEPRECATED
display_errors = On
display_startup_errors = On
error_log = /var/log/php/error.log
log_errors = On

memory_limit = 512M
max_execution_time = 300
max_input_vars = 5000
upload_max_filesize = 100M
post_max_size = 100M

date.timezone = Europe/Paris

; Dev OPcache — revalidate on every request so file edits are picked up
opcache.enable = 1
opcache.validate_timestamps = 1
opcache.revalidate_freq = 0

zend.assertions = 1
```

## `docker/php/www.conf` → mounted at `/usr/local/etc/php-fpm.d/zzz-custom.conf`

```ini
[www]
; LOAD-BEARING: PHP-FPM strips env by default. Without this, $_ENV[...] used by
; settings.php for DB/Redis/SMTP config is empty and the site cannot connect.
clear_env = no
```

## `docker/php/xdebug.ini` → mounted at `/usr/local/etc/php/conf.d/docker-php-ext-xdebug.ini`

```ini
[xdebug]
xdebug.mode = develop,debug
xdebug.client_host = host.docker.internal
xdebug.client_port = 9003
xdebug.start_with_request = yes
xdebug.idekey = PHPSTORM
xdebug.max_nesting_level = 512
xdebug.var_display_max_depth = 10
xdebug.var_display_max_children = 256
xdebug.var_display_max_data = 1024
```

> The runtime toggle is the `XDEBUG_MODE` env var (compose `environment`), not
> this file — set `XDEBUG_MODE=off` in `.env` for performance. On Linux hosts,
> add `extra_hosts: ["host.docker.internal:host-gateway"]` to the php service
> (Docker Desktop on macOS provides it automatically).

## `docker/apache/Dockerfile` — thin reverse proxy to PHP-FPM

```dockerfile
FROM httpd:2.4-alpine
RUN sed -i \
    -e 's/#LoadModule proxy_module/LoadModule proxy_module/' \
    -e 's/#LoadModule proxy_fcgi_module/LoadModule proxy_fcgi_module/' \
    -e 's/#LoadModule rewrite_module/LoadModule rewrite_module/' \
    -e 's/#LoadModule headers_module/LoadModule headers_module/' \
    -e 's/#LoadModule expires_module/LoadModule expires_module/' \
    /usr/local/apache2/conf/httpd.conf \
    && mkdir -p /usr/local/apache2/conf/vhosts \
    && echo "IncludeOptional /usr/local/apache2/conf/vhosts/*.conf" >> /usr/local/apache2/conf/httpd.conf
COPY vhost.conf /usr/local/apache2/conf/vhosts/drupal.conf
EXPOSE 80
```

## `docker/apache/vhost.conf`

```apache
<VirtualHost *:80>
    ServerName localhost
    DocumentRoot /var/www/html/web

    <Directory /var/www/html/web>
        Options -Indexes +FollowSymLinks
        AllowOverride All            # required for Drupal .htaccess
        Require all granted
    </Directory>

    # Forward PHP to the php-fpm container
    <FilesMatch "\.php$">
        SetHandler "proxy:fcgi://php:9000"
    </FilesMatch>

    # Dev only: defeat Drupal's far-future Expires on theme assets so Vite/Gulp
    # rebuilds are picked up without a hard refresh. (akena variant — optional)
    <LocationMatch "^/themes/custom/[^/]+/(css|js|images)/">
        Header set Cache-Control "no-store, no-cache, must-revalidate"
    </LocationMatch>

    ErrorLog /proc/self/fd/2
    CustomLog /proc/self/fd/1 combined
</VirtualHost>
```

## `docker/node/Dockerfile`

The base is always `node:22-alpine` (runs natively on arm64 **and** amd64 — do
NOT force `platform: linux/amd64`, and do NOT create a `Dockerfile.x64`; that is
a dead Lando-era leftover). The build toolchain + `CFLAGS` block is **only**
needed when the frontend uses `gulp-imagemin` / `imagemin-optipng` (see
`frontend-build.md`). Minimal form for a project without native imagemin:

```dockerfile
FROM node:22-alpine
WORKDIR /var/www/html
```

Form required when `imagemin-optipng` is a dependency (compiles optipng/libpng
from source; the prebuilt binary is glibc/x86-64 and fails on Alpine musl / ARM):

```dockerfile
FROM node:22-alpine
RUN apk add --no-cache \
    autoconf automake libtool build-base nasm zlib-dev libpng-dev giflib-dev
# libpng's ARM-NEON path references symbols it doesn't compile on arm64 → disable it
ENV CFLAGS="-DPNG_ARM_NEON_OPT=0" \
    CPPFLAGS="-DPNG_ARM_NEON_OPT=0"
WORKDIR /var/www/html
```

## `.dockerignore` (repo root)

```
.git
.idea
node_modules
vendor
web/core
web/modules/contrib
web/themes/contrib
web/libraries
*.sql
*.sql.gz
storage/private
storage/tmp
.DS_Store
```
