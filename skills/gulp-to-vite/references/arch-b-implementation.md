# Arch B — complete implementation (verified on Project B)

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
    "@vitejs/plugin-basic-ssl": "^2.3.0",
    "cheerio": "^1.2.0",
    "esbuild": "^0.28.2",
    "postcss": "^8.5.31",
    "postcss-pxtorem": "^6.1.0",
    "sass": "^1.105.2",
    "sharp": "^0.35.5",
    "svgo": "^4.1.0",
    "tinyglobby": "^0.2.17",
    "vite": "^8.3.4"
  },
  "engines": {
    "node": ">=24"
  }
}
```

These versions are a baseline. Install the current ones instead of copying them
(see "Versions" below). `engines.node` = the Node LTS major of the node image.

### Versions: latest packages, Node LTS

- **Node**: the current **Active LTS** major, i.e. the newest major whose `lts`
  date has passed on `https://endoflife.date/api/nodejs.json`. Odd majors and a
  "Current" even major that has not reached its LTS date yet are never the
  target. Use the same major in the compose `node` service
  (`image: node:<major>-alpine`; once imagemin is gone, delete a
  `FROM` + `WORKDIR`-only `docker/node/Dockerfile`), `engines.node`, and the **CI image** (it builds the
  production assets: a CI on an older Node is a mismatch to fix in the same MR,
  or to list as a prerequisite when the image comes from another repository).
- **Packages**: install every devDependency at its latest version in the
  container, then read each package's major-version changelog (Vite and Sass
  majors change config and deprecations):

  ```bash
  make npm c='install -D vite@latest sass@latest esbuild@latest postcss@latest postcss-pxtorem@latest cheerio@latest tinyglobby@latest sharp@latest svgo@latest'
  make npm c='install -D @vitejs/plugin-basic-ssl@latest'   # TLS Option A only
  ```

- **No `imagemin-*`, no `fast-glob`.** The imagemin encoders download and compile
  binaries through `bin-build` / `bin-wrapper`, which pull `decompress`, `got`,
  `semver-regex`, `http-cache-semantics` and an old `cross-spawn`. Several of
  them carry critical advisories that have **no fix**: `npm audit fix` cannot
  clear them. `fast-glob` brings `micromatch` → `braces` (another unfixed
  advisory). `sharp` + `svgo` ship prebuilt binaries, and `tinyglobby` is the
  glob library Vite itself uses.
- **`sass` ≥ 1.92.0 changes the compiled CSS** when the source still has
  `mixed-decls` (declarations after a nested rule). The trailing declarations
  are emitted as a separate rule *after* the nested children, which reorders the
  cascade. On one reference project, `@latest` split seven rules
  (`.btn{…;margin-top:25px}` became `.btn{…}` + a later `.btn{margin-top:25px}`).
  Snapshot the outputs **before** the bump and compare them after (see Verify).
  If the CSS differs, pin `"sass": "~1.91.0"`, the last version that keeps the
  old output, and list the `sass-migrator` mixed-decls fix as the follow-up that
  unpins it. Find the boundary on another project with
  `npx -y sass@<v> --style=compressed --quiet <entry>.scss` against the snapshot.
- **npm 11 (Node 24) blocks install scripts** until they are reviewed:
  `npm warn install-scripts … not yet covered by allowScripts`. Decide each one
  and commit the result (`allowScripts` in `package.json`):

  ```bash
  make npm c='install-scripts ls'
  make npm c='install-scripts approve esbuild'          # binary check of the official package
  make npm c='install-scripts deny @parcel/watcher'     # node-gyp rebuild; the prebuilt optional dep is enough
  ```

  Approve only what the build needs. A `node-gyp` rebuild of a package that ships
  prebuilt binaries is a deny.
- **Quote `>` in a `make` argument.** `make npm c='pkg set engines.node=>=24'`
  goes through the shell again inside the Makefile recipe: `>` becomes a
  redirection, writes an empty file named `=24` at the root, and sets nothing.
  Edit `package.json` directly, or escape the value
  (`c='pkg set "engines.node=>=24"'`), then check with `git status`.

Delete `gulpfile.js`. After `npm install`, ~900 gulp packages drop out.

## `vite.config.mjs`

```js
import { defineConfig, loadEnv } from 'vite';
import basicSsl from '@vitejs/plugin-basic-ssl';
import ViteSass from './plugins/vite-sass.js';
import ViteCopyJs from './plugins/vite-copy-js.js';
import ViteImages from './plugins/vite-images.js';
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
          { glob: theme + '/src/sass/paragraphs_custom/**/*.scss', base: theme + '/src/sass', outDir: theme + '/css/theme' },
          { entries: [{ in: admin + '/styles/src/theme.scss', out: admin + '/styles/dist/theme.css' }] },
        ],
      }),
      ViteCopyJs({ dev, srcDir: theme + '/src/js', destDir: theme + '/js' }),
      ViteImages({ srcDir: theme + '/src/images', destDir: theme + '/images' }),
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
      // root is the whole docroot, served raw. Never `cors: true`: any page the
      // developer visits could then read it. Only the Drupal site may fetch.
      cors: { origin: env.HOME_URL },
      // Replaces Vite's default deny list, so the defaults are repeated.
      fs: {
        deny: ['.env', '.env.*', '*.{crt,pem}', '**/.git/**', '**/*.php', '**/*.inc', '**/*.yml'],
      },
      allowedHosts: ['.dev.localhost'],
      hmr: { host: 'localhost', protocol: 'wss', clientPort: 3009 },
      watch: {
        usePolling: true, interval: 300,            // Docker Desktop macOS: inotify not forwarded
        // Polling cost scales with file count: core + contrib are tens of
        // thousands of files that never change during theme work.
        ignored: [
          '**/themes/custom/*/css/**', '**/themes/custom/*/js/**', '**/themes/custom/*/images/**',
          '**/sites/*/files/**', '**/node_modules/**',
          '**/core/**', '**/modules/contrib/**', '**/themes/contrib/**', '**/libraries/**',
        ],
      },
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
  // No 'legacy-js-api' here: that warning only comes from the legacy
  // render()/renderSync() API, and this plugin uses sass.compile().
  const silenceDeprecations = ['color-functions', 'global-builtin', 'import'];
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
      const { glob } = await import('tinyglobby');
      const base = path.resolve(process.cwd(), group.base);
      const files = await glob(group.glob, { cwd: process.cwd(), ignore: ['**/_*.scss'] });
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

## `plugins/vite-images.js` (sharp + svgo)

```js
import { promises as fs } from 'fs';
import path from 'path';
import sharp from 'sharp';
import { optimize } from 'svgo';

export default function ViteImages({ srcDir, destDir }) {
  const absSrc = path.resolve(process.cwd(), srcDir);
  const absDest = path.resolve(process.cwd(), destDir);

  async function encode(file, input) {
    switch (path.extname(file).toLowerCase()) {
      case '.png':
        return sharp(input).png({ compressionLevel: 9, effort: 10 }).toBuffer();
      case '.jpg':
      case '.jpeg':
        return sharp(input).jpeg({ quality: 75, progressive: true, mozjpeg: true }).toBuffer();
      case '.svg':
        return Buffer.from(optimize(input.toString('utf8'), { path: file, plugins: ['removeViewBox'] }).data);
      default:
        return input;
    }
  }

  async function optimizeOne(rel) {
    const input = await fs.readFile(path.join(absSrc, rel));
    const output = await encode(rel, input);
    const out = path.join(absDest, rel);
    await fs.mkdir(path.dirname(out), { recursive: true });
    // Never ship a re-encode that is bigger than its source.
    await fs.writeFile(out, output.length < input.length ? output : input);
  }

  async function optimizeAll() {
    const { glob } = await import('tinyglobby');
    const files = await glob('**/*.{png,jpg,jpeg,gif,svg,webp}', { cwd: absSrc, ignore: ['sprites/**'] });
    await Promise.all(files.map(optimizeOne));
    console.log('\x1b[32m%s\x1b[0m', `🚀 Images optimised (${files.length})`);
  }

  return {
    name: 'vite-images',
    buildStart() { return optimizeAll(); },
    async handleHotUpdate({ file, server }) {
      if (/\.(png|jpe?g|gif|svg|webp)$/.test(file) && file.startsWith(absSrc + path.sep) && !file.includes('/sprites/')) {
        await optimizeOne(path.relative(absSrc, file)); server.ws.send({ type: 'full-reload', path: '*' }); return [];
      }
    },
  };
}
```

### Encoder equivalence with the old imagemin task

The migration is iso-functional, so each encoder must match what Gulp did:

| Old (imagemin) | sharp / svgo | Trap |
|---|---|---|
| `optipng({ optimizationLevel: 5 })`, lossless | `.png({ compressionLevel: 9, effort: 10 })` | **never `palette: true`**: it quantises to 256 colours (banding on gradients, degraded alpha), a lossy change a reviewer will flag |
| `mozjpeg({ quality: 75, progressive: true })` | `.jpeg({ quality: 75, progressive: true, mozjpeg: true })` | — |
| `gifsicle({ interlaced: true })` | none, copied as-is | say so in the MR |
| `svgo({ plugins: [{ name: 'removeViewBox' }] })` | `optimize(svg, { plugins: ['removeViewBox'] })` | a `plugins` list **replaces** `preset-default`. Copy the old list exactly; do not switch to `preset-default` in passing. Read the gulpfile's real options rather than these values |
| `.webp` with no imagemin plugin | copied as-is | — |

A lossy setting for the size win is a separate change, validated visually.

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
      if (!viewBox) {                              // else the symbol ships viewBox="undefined"
        console.warn('\x1b[33m%s\x1b[0m', `⚠ vite-icon-sprite: ${file} has no viewBox, skipped`);
        continue;
      }
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
  - *Option A* — publish the port **on loopback only**:
    `ports: ["127.0.0.1:3009:3009"]`. A bare `"3009:3009"` binds 0.0.0.0 and
    serves the raw docroot to the whole LAN.
  - *Option B (Traefik)* — join the `traefik-public` network and add labels so
    Vite is reachable at the trusted `<project>-vite.dev.localhost`; also pass
    `VITE_DEV_URL` (read by `vite.config.mjs`) and `HOME_URL` (the CORS origin).
    **Publish no port**: Traefik reaches Vite over the Docker network, and a
    published port only adds LAN exposure and cross-project port clashes.

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
docker run --rm -v "$(pwd)":/var/www/html -w /var/www/html node:<LTS>-alpine \
  sh -c 'rm -rf node_modules && npm install --no-audit --no-fund && npm run build'
```

Expect all four "🚀 …" lines incl. **Images optimised**. Compare with the
snapshot taken from the Gulp build (or from the build before a dependency bump):

```bash
S=<scratchpad>/before; T=web/themes/custom/<theme>
diff -rq "$S/css" "$T/css"; diff -rq "$S/js" "$T/js"; cmp "$S/images/sprites.svg" "$T/images/sprites.svg"
diff <(cd "$S/images" && find . -type f | sort) <(cd "$T/images" && find . -type f | sort)
```

Target: CSS, JS and sprite byte-identical, and the same image list with no
noticeable size regression (a few bytes on a PNG where optipng beat sharp is
normal: list them in the MR). Then the audit:

```bash
make npm c='audit --include=dev'      # target: found 0 vulnerabilities
make npm c='ls imagemin fast-glob gulp' # target: (empty)
```

Each advisory left must be listed in the MR with its path (`npm ls <pkg>`) and
why it stays (no fix upstream, dev-only, not reachable from the build).
```
