# Arch B — complete implementation (verified on ginger-cebtp)

Copy-pasteable, iso-functional. Replace `<theme>` with the theme folder name
(read from the `THEME_FOLDER` env), and adjust the exposed port. Every asset is
written to the **legacy** output folders so `*.libraries.yml` stays untouched.

## `package.json` (root)

```json
{
  "name": "<project>",
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "devDependencies": {
    "@vitejs/plugin-basic-ssl": "^2.0.0",
    "cheerio": "^1.0.0",
    "esbuild": "^0.24.0",
    "fast-glob": "^3.3.3",
    "imagemin": "^9.0.0",
    "imagemin-gifsicle": "^7.0.0",
    "imagemin-mozjpeg": "^10.0.0",
    "imagemin-optipng": "^8.0.0",
    "imagemin-svgo": "^11.0.1",
    "postcss": "^8.4.14",
    "postcss-pxtorem": "^6.0.0",
    "sass": "^1.79.4",
    "vite": "^6.2.3"
  }
}
```

Delete `gulpfile.js`. After `npm install`, ~900 gulp packages drop out.

## `vite.config.mjs`

```js
import { defineConfig, loadEnv } from 'vite';
import basicSsl from '@vitejs/plugin-basic-ssl';
import ViteSass from './plugins/vite-sass.js';
import ViteCopyJs from './plugins/vite-copy-js.js';
import ViteImagemin from './plugins/vite-imagemin.js';
import ViteIconSprite from './plugins/vite-icon-sprite.js';

const PXTOREM = { propList: ['font-size'], replace: true, unitPrecision: 3 };

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const dev = mode !== 'production';
  const theme = 'web/themes/custom/' + (env.THEME_FOLDER || '<theme>');
  const admin = 'web/themes/custom/<admin_theme>';
  const noopEntry = 'virtual:noop-entry';

  return {
    plugins: [
      {
        name: 'live-reload-templates',
        handleHotUpdate({ file, server }) {
          if (/\.(twig|theme|php|inc|yml)$/.test(file)) {
            server.ws.send({ type: 'full-reload', path: '*' });
          }
        },
      },
      basicSsl(),
      ViteSass({
        dev,
        pxtorem: PXTOREM,
        groups: [
          { entries: [{ in: theme + '/src/sass/style.scss', out: theme + '/css/style.css' }] },
          { glob: theme + '/src/sass/paragraphs_sofreco/**/*.scss', base: theme + '/src/sass', outDir: theme + '/css/theme' },
          { entries: [{ in: admin + '/styles/src/theme.scss', out: admin + '/styles/dist/theme.css' }] },
        ],
      }),
      ViteCopyJs({ dev, srcDir: theme + '/src/js', destDir: theme + '/js' }),
      ViteImagemin({ srcDir: theme + '/src/images', destDir: theme + '/images' }),
      ViteIconSprite({ srcDir: theme + '/src/images/sprites', destFile: theme + '/images/sprites.svg' }),
      {
        name: 'noop-entry',
        resolveId(id) { if (id === noopEntry) return '\0' + noopEntry; },
        load(id) { if (id === '\0' + noopEntry) return 'export default {};'; },
      },
    ],
    build: {
      write: false,                                 // Rollup emits nothing; plugins write everything.
      rollupOptions: { input: noopEntry },
    },
    root: 'web',
    server: {
      host: true,
      strictPort: true,
      port: 3009,                                   // adjust per project; collides across GM projects
      origin: env.HOME_URL,
      cors: true,
      allowedHosts: ['.dev.localhost'],
      hmr: { host: 'localhost', protocol: 'wss', clientPort: 3009 },
      watch: { usePolling: true, interval: 300 },   // Docker Desktop macOS: inotify not forwarded
    },
  };
});
```

### TLS & HMR: pick one — direct `:3009` or behind Traefik

The dev page is HTTPS (`*.dev.localhost` via the shared Traefik), so the
`@vite/client` it loads must be HTTPS too (else mixed-content blocked). Two ways
to give the dev server a cert. **Decide with the user** — default to A unless
they want to stop clicking through the cert warning.

**Option A — `basic-ssl` on `localhost:3009` (default, simplest, fleet-standard).**
The config above. Vite terminates TLS with a self-signed cert. Cost: the browser
shows an **untrusted-cert warning that must be accepted once per cert** — and the
cert is regenerated on every `npm install` (it lives in `node_modules/.vite/`),
so a fresh install ⇒ re-accept. The dev URL is `https://localhost:3009`. No
compose/Traefik changes needed beyond publishing the port.

**Option B — behind Traefik on `<project>-vite.dev.localhost` (no cert prompt).**
Route the dev server through the same shared Traefik as the app, so it inherits
the **trusted mkcert `*.dev.localhost` wildcard** (verify the socle serves it:
`openssl s_client -connect <project>-adminer.dev.localhost:443 | openssl x509
-noout -issuer` → `mkcert development CA`). Zero warnings, and it survives
`npm install`. Deltas vs the config above:

```js
// drop the import and the basicSsl() plugin entry — Traefik terminates TLS,
// Vite serves plain HTTP inside the container.
// - import basicSsl from '@vitejs/plugin-basic-ssl';
// - basicSsl(),

// Vite dev URL comes from the compose env (see Docker section):
const devUrl = env.VITE_DEV_URL || 'https://localhost:3009';
const devHost = new URL(devUrl).hostname;

// server:
  origin: devUrl,
  hmr: { host: devHost, protocol: 'wss', clientPort: 443 },  // wss over Traefik:443
```

Then drop `@vitejs/plugin-basic-ssl` from `package.json`. Keep `port: 3009`
(Traefik proxies to it) and `allowedHosts: ['.dev.localhost']` (already covers
the vite host). See the Docker and dev-wiring sections below for the matching
compose labels and `@vite/client` URL.

## `plugins/vite-sass.js`

```js
import { promises as fs } from 'fs';
import path from 'path';
import * as sass from 'sass';
import postcss from 'postcss';
import pxtorem from 'postcss-pxtorem';

export default function ViteSass({ groups, pxtorem: pxtoremOptions, dev }) {
  const silenceDeprecations = ['legacy-js-api', 'color-functions', 'global-builtin', 'import'];
  const processor = postcss([pxtorem(pxtoremOptions)]);

  async function compileEntry(input, output) {
    const result = sass.compile(input, {
      style: 'compressed', sourceMap: dev, sourceMapIncludeSources: dev, silenceDeprecations,
    });
    const processed = await processor.process(result.css, {
      from: input, to: output, map: dev ? { inline: false, prev: result.sourceMap } : false,
    });
    await fs.mkdir(path.dirname(output), { recursive: true });
    let css = processed.css;
    if (dev && processed.map) {
      await fs.writeFile(`${output}.map`, processed.map.toString());
      css += `\n/*# sourceMappingURL=${path.basename(output)}.map */`;
    }
    await fs.writeFile(output, css);
  }

  async function compileGroup(group) {
    for (const { in: input, out } of group.entries ?? []) {
      await compileEntry(path.resolve(process.cwd(), input), path.resolve(process.cwd(), out));
    }
    if (group.glob) {
      const { default: fg } = await import('fast-glob');
      const base = path.resolve(process.cwd(), group.base);
      const files = await fg(group.glob, { cwd: process.cwd(), ignore: ['**/_*.scss'] });
      for (const file of files) {
        const abs = path.resolve(process.cwd(), file);
        const rel = path.relative(base, abs).replace(/\.scss$/, '.css');
        await compileEntry(abs, path.resolve(process.cwd(), group.outDir, rel));
      }
    }
  }

  async function compileAll() {
    for (const group of groups) await compileGroup(group);
    console.log('\x1b[32m%s\x1b[0m', '🚀 SASS compiled');
  }

  return {
    name: 'vite-sass',
    buildStart() { return compileAll(); },
    async handleHotUpdate({ file, server }) {
      if (file.endsWith('.scss')) { await compileAll(); server.ws.send({ type: 'full-reload', path: '*' }); return []; }
    },
  };
}
```

## `plugins/vite-copy-js.js`

```js
import { promises as fs } from 'fs';
import path from 'path';
import { transform } from 'esbuild';
import { normalizePath } from 'vite';

export default function ViteCopyJs({ srcDir, destDir, dev }) {
  async function minifyFile(absSrc) {
    const rel = path.relative(path.resolve(process.cwd(), srcDir), absSrc);
    const absDest = path.resolve(process.cwd(), destDir, rel);
    const code = await fs.readFile(absSrc, 'utf8');
    const result = await transform(code, { minify: true, loader: 'js', sourcemap: dev, sourcefile: rel });
    await fs.mkdir(path.dirname(absDest), { recursive: true });
    let out = result.code;
    if (dev && result.map) { await fs.writeFile(`${absDest}.map`, result.map); out += `\n//# sourceMappingURL=${path.basename(absDest)}.map`; }
    await fs.writeFile(absDest, out);
  }
  async function walk(dir) {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    const files = [];
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) files.push(...(await walk(full)));
      else if (e.name.endsWith('.js')) files.push(full);
    }
    return files;
  }
  async function copyAll() {
    const files = await walk(path.resolve(process.cwd(), srcDir));
    for (const f of files) await minifyFile(f);
    console.log('\x1b[32m%s\x1b[0m', '🚀 JS minified & copied');
  }
  return {
    name: 'vite-copy-js',
    enforce: 'pre',
    buildStart() { return copyAll(); },
    async handleHotUpdate({ file, server }) {
      if (normalizePath(file).includes(normalizePath(srcDir)) && file.endsWith('.js')) {
        await minifyFile(file); server.ws.send({ type: 'full-reload', path: '*' }); return [];
      }
    },
  };
}
```

## `plugins/vite-imagemin.js`

```js
import { promises as fs } from 'fs';
import path from 'path';
import imagemin from 'imagemin';
import gifsicle from 'imagemin-gifsicle';
import mozjpeg from 'imagemin-mozjpeg';
import optipng from 'imagemin-optipng';
import svgo from 'imagemin-svgo';

export default function ViteImagemin({ srcDir, destDir }) {
  const plugins = [
    gifsicle({ interlaced: true }),
    mozjpeg({ quality: 75, progressive: true }),
    optipng({ optimizationLevel: 5 }),
    svgo({ plugins: [{ name: 'removeViewBox', active: true }] }),
  ];
  async function optimizeAll() {
    const { default: fg } = await import('fast-glob');
    const absSrc = path.resolve(process.cwd(), srcDir);
    const absDest = path.resolve(process.cwd(), destDir);
    const files = await fg('**/*.{png,jpg,jpeg,gif,svg,webp}', { cwd: absSrc, ignore: ['sprites/**'] });
    for (const rel of files) {
      const buffer = await imagemin.buffer(await fs.readFile(path.join(absSrc, rel)), { plugins });
      const out = path.join(absDest, rel);
      await fs.mkdir(path.dirname(out), { recursive: true });
      await fs.writeFile(out, buffer);
    }
    console.log('\x1b[32m%s\x1b[0m', '🚀 Images optimised');
  }
  return {
    name: 'vite-imagemin',
    buildStart() { return optimizeAll(); },
    async handleHotUpdate({ file, server }) {
      if (/\.(png|jpe?g|gif|svg|webp)$/.test(file) && file.includes('/src/images/') && !file.includes('/sprites/')) {
        await optimizeAll(); server.ws.send({ type: 'full-reload', path: '*' }); return [];
      }
    },
  };
}
```

## `plugins/vite-icon-sprite.js`

```js
import { promises as fs } from 'fs';
import path from 'path';
import * as cheerio from 'cheerio';

export default function ViteIconSprite({ srcDir, destFile }) {
  async function generate() {
    const iconsDir = path.resolve(process.cwd(), srcDir);
    const files = await fs.readdir(iconsDir);
    let symbols = '';
    for (const file of files) {
      if (!file.endsWith('.svg')) continue;
      let svg = await fs.readFile(path.join(iconsDir, file), 'utf8');
      const $svg = cheerio.load(svg, { xmlMode: true })('svg');
      if ($svg.length === 0) continue;
      const viewBox = $svg.attr('viewBox');
      const id = file.replace(/\.svg$/, '');
      svg = svg
        .replace(/<\?xml[^>]*>/g, '').replace(/<!--[\s\S]*?-->/g, '').replace(/<style[\s\S]*?<\/style>/g, '')
        .replace(/\r?\n|\r/g, '').replace(/\t/g, '').replace(/\s{2,}/g, ' ')
        .replace(/ id="[^"]*"/g, '').replace(/ version="[^"]*"/g, '')
        .replace(/ (x|y|width|height|fill|stroke|xmlns:xlink|xml:space)="[^"]*"/g, '')
        .replace(/<svg[^>]*>/, `<symbol id="${id}" viewBox="${viewBox}">`).replace(/<\/svg>/, '</symbol>');
      symbols += svg;
    }
    const sprite = '<?xml version="1.0" encoding="UTF-8"?>'
      + '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">' + symbols + '</svg>';
    const out = path.resolve(process.cwd(), destFile);
    await fs.mkdir(path.dirname(out), { recursive: true });
    await fs.writeFile(out, sprite);
    console.log('\x1b[32m%s\x1b[0m', '🚀 SVG sprite generated');
  }
  return {
    name: 'vite-icon-sprite',
    buildStart() { return generate(); },
    async handleHotUpdate({ file, server }) {
      if (file.includes('/src/images/sprites') && file.endsWith('.svg')) {
        await generate(); server.ws.send({ type: 'full-reload', path: '*' }); return [];
      }
    },
  };
}
```

## Drupal dev wiring (Arch B minimal)

`<theme>.libraries.yml` — add at the top:

```yaml
# Vite dev-server HMR client. Attached only in local (see theme/vite.inc);
# never loaded on preprod/prod.
hot-replacement:
  header: true
  js:
    # Option A (basic-ssl):
    https://localhost:3009/@vite/client: { type: external, attributes: { type: module }, preprocess: false }
    # Option B (Traefik) — use this URL instead, hardcode the project name
    # (YAML can't interpolate env): https://<project>-vite.dev.localhost/@vite/client
```

Dev-only attach. **First check whether the theme ALREADY implements
`<theme>_page_attachments_alter()`** (grep it — GM themes that load
`theme/*.inc` often do, e.g. in `html.inc`). If it exists, **merge the snippet
into that function** — a second copy in a new `vite.inc` throws a fatal
`Cannot redeclare function <theme>_page_attachments_alter()`. Only create
`<theme>/theme/vite.inc` if no implementation exists yet.

```php
<?php

/**
 * Implements hook_page_attachments_alter().
 *
 * Attaches the Vite HMR client in local development only, so the markup served
 * on preprod and production is byte-identical to before the Gulp migration.
 * The client is a no-op unless `make npm-dev` is running.
 */
function <theme>_page_attachments_alter(array &$attachments) {
  if (getenv('APP_ENV') === 'local') {
    $attachments['#attached']['library'][] = '<theme>/hot-replacement';
  }
}
```

### Read the source your dotenv loader actually populates

`getenv()` above is correct **only** when `.env` is loaded with `symfony/dotenv`
and `usePutenv(TRUE)`. Check `load.environment.php` first:

| Loader in `load.environment.php` | `$_ENV` / `$_SERVER` | `getenv()` | Gate |
|---|---|---|---|
| `vlucas/phpdotenv` — `Dotenv::createImmutable(__DIR__)->safeLoad()` | populated | **`FALSE`** | `($_ENV['APP_ENV'] ?? NULL) === 'local'` |
| `symfony/dotenv` — `(new Dotenv())->usePutenv(TRUE)->bootEnv(…)` | populated | populated | `getenv('APP_ENV') === 'local'` |
| none (compose `environment:` only) | needs `clear_env = no` **and** `E` in `variables_order` | needs `clear_env = no` | `getenv('APP_ENV') === 'local'` |

Preferred fix when the project is still on `vlucas/phpdotenv`: migrate the loader
once, so every consumer can read `getenv()` and the gate stays a one-liner.

```php
// load.environment.php — composer require drupal/dotenv (pulls symfony/dotenv)
use Symfony\Component\Dotenv\Dotenv;

(new Dotenv())->usePutenv(TRUE)->bootEnv(DRUPAL_ROOT . '/../.env');
```

`DRUPAL_ROOT` is available here despite this file running from Composer's
`autoload.files`: `drupal/core` declares `includes/bootstrap.inc` in its own
`autoload.files`, and dependency files load before the root package's.

Whichever source you read, **read exactly one.** A
`$_ENV['APP_ENV'] ?? getenv('APP_ENV') ?: ''` chain looks defensive but only
hides which source is authoritative — the fail-closed behaviour comes from the
strict `=== 'local'`, which already rejects `FALSE`, `''`, `prod` and `preprod`.
And never default the fallback to `'local'`: that is fail-**open**, and a
production deploy with an empty `APP_ENV` would emit a `<script>` pointing at
`https://<project>-vite.dev.localhost/@vite/client` on live pages. Local always
sets `APP_ENV=local` (compose passes it, and a shared `base.settings.php`
typically refuses to configure the database without it), so an empty value never
legitimately means "local".

### Verify

Five cases, plus one real request. Overriding the superglobal is **not** a test of
the absent case — `getenv()` still reads the container's real environment and the
test falsely passes — so drop the variable with `env -u`:

```bash
# local / prod / preprod / empty
docker compose exec -T --user www-data php sh -c '
for v in local prod preprod ""; do APP_ENV="$v" php -r \
  "printf(\"%-8s attach=%s\n\", getenv(\"APP_ENV\") ?: \"(empty)\", getenv(\"APP_ENV\") === \"local\" ? \"YES\" : \"no\");"
done'

# genuinely absent — must print attach=no
docker compose exec -T --user www-data php env -u APP_ENV php -r \
  'printf("absent attach=%s\n", getenv("APP_ENV") === "local" ? "YES" : "no");'

# and the gate on a real FPM request — must print 1 locally
curl -ksS https://<project>.dev.localhost/ | grep -c '@vite/client'
```

The `curl` is the one that matters: a passing CLI check proves nothing about the
FPM worker, which sees a different environment (`clear_env`).

## Docker / Makefile / CI

- **compose `node` service**: keep it idle (`command: ["tail","-f","/dev/null"]`)
  and run Vite via `make npm-dev`; drop dead `BS_*` env; set `THEME_FOLDER`.
  - *Option A* — just publish the port: `ports: ["3009:3009"]`.
  - *Option B (Traefik)* — join the `traefik-public` network and add labels so
    Vite is reachable at the trusted `<project>-vite.dev.localhost`; also pass
    `VITE_DEV_URL` (read by `vite.config.mjs`). Keep the published port too for
    optional direct access.

    ```yaml
    node:
      environment:
        HOME_URL: https://${COMPOSE_PROJECT_NAME}.dev.localhost
        VITE_DEV_URL: https://${COMPOSE_PROJECT_NAME}-vite.dev.localhost
        THEME_FOLDER: ${THEME_FOLDER:-<theme>}
      networks: [app-internal, traefik-public]
      labels:
        - "traefik.enable=true"
        - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-vite.rule=Host(`${COMPOSE_PROJECT_NAME}-vite.dev.localhost`)"
        - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-vite.entrypoints=websecure"
        - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-vite.tls=true"
        - "traefik.http.routers.${COMPOSE_PROJECT_NAME}-vite.service=${COMPOSE_PROJECT_NAME}-vite"
        - "traefik.http.services.${COMPOSE_PROJECT_NAME}-vite.loadbalancer.server.port=3009"
        - "traefik.docker.network=traefik-public"
    ```

    Traefik proxies wss transparently, so HMR works over `wss://…:443` with no
    extra config. Recreate the service (`docker compose up -d --force-recreate
    node`) after editing labels.
- **Makefile**: `install`/`init` run `npm run build` (not `gulp deploy`); keep
  `npm-dev` (`npm run dev`) / `npm-build` (`npm run build`); remove `gulp`,
  `gulp-watch`, `gulp-deploy`, stale `npm-watch`; update `.PHONY` + help text.
- **`.gitlab-ci.yml`**: in the build job replace `gulp deploy` with `npm run build`.
  **Leave the artifact `paths:` unchanged** (`css/ fonts/ images/ js/` +
  admin `styles/dist`) — Arch B writes to the same folders. The root `npm ci`
  (which now installs Vite) already runs in the `npm` preparation job.
- **apache vhost**: add the dev-only no-cache `LocationMatch` for theme assets
  (see SKILL.md Step 3.6). Remember `vhost.conf` is `COPY`ed into the image, so it
  needs `docker compose build apache` + recreate, and teammates need `make rebuild`.

## Local caching that must be disabled (Arch B prerequisite)

Arch B serves plain on-disk files, so anything caching in front of them defeats
HMR. Put these in the project's **tracked** shared local settings
(`base.settings.php` or equivalent), never a personal `settings.php` — they are
settings-level `$config` overrides, so `config/sync` and production are untouched:

```php
// Aggregation rebuilds sites/default/files/css/css_<hash>.css from the asset
// LIST, not file contents — recompiling never invalidates it.
$config['system.performance']['css']['preprocess'] = FALSE;
$config['system.performance']['js']['preprocess'] = FALSE;

// config/sync often ships 21600 (6h) — anonymous pages get a long Cache-Control.
$config['system.performance']['cache']['page']['max_age'] = 0;
```

Plus the render-cache nulling that the Docker/local settings usually already have
(`render`, `page`, `dynamic_page_cache` → `cache.backend.null`).

## Verify build in-container (authoritative)

```bash
docker run --rm -v "$(pwd)":/var/www/html -w /var/www/html <project>-node:latest \
  sh -c 'rm -rf node_modules && npm install --no-audit --no-fund && npm run build'
```

Expect all four "🚀 …" lines incl. **Images optimised**. `spawn ENOEXEC` /
`rosetta error … ld-linux-x86-64.so.2` only happens on the host or a container
holding an x86 prebuilt binary — the project's own node image compiles
`imagemin-*` from source for ARM/Alpine.
```
