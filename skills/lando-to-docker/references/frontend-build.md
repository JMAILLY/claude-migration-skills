# Frontend build in the node container

The Lando `node` service ran the theme build (often `gulp` with a forced
`platform: linux/amd64`). In Docker, the `node` service **idles**
(`command: tail -f /dev/null`) and the build runs through the Makefile
(`make npm-dev` / `make npm-build` / `make npm c=...`), i.e.
`docker compose exec node npm …`. Base image is always `node:22-alpine`
(multi-arch — no amd64 forcing).

## Decision 1 — does the node image need the build toolchain?

Check `package.json` for `gulp-imagemin` / `imagemin-optipng` (or any `imagemin-*`
that shells out to a native binary):

```bash
grep -E 'imagemin|optipng|mozjpeg|gifsicle' package.json web/themes/custom/*/package.json 2>/dev/null
```

- **Match found** → use the toolchain form of `docker/node/Dockerfile` (apk
  build-base + `CFLAGS=-DPNG_ARM_NEON_OPT=0`, see `docker-images.md`). The
  prebuilt `optipng` binary is glibc/x86-64 and fails on Alpine musl / ARM64, so
  it compiles from source; the NEON flag lets libpng link on arm64.
- **No match** (pure esbuild/Vite/Tailwind) → the minimal `node:22-alpine` form
  is enough.

> When migrating a Gulp project, also consider dropping the fragile
> `gulp-imagemin` `mozjpeg`/`optipng` plugins entirely — that removes the whole
> toolchain requirement. The `gulp-to-vite` skill covers replacing Gulp; this
> skill only needs the build to *run* in the container.

## Decision 2 — how the dev server / HMR is wired

`make npm-dev` starts the dev server; it is published on `VITE_SERVER_PORT` and
also exposed via Traefik at `https://<project>-vite.dev.localhost`. Because
Traefik terminates TLS, the HMR socket must be told it is behind HTTPS.

### Gulp / BrowserSync

BrowserSync proxies the site and injects a `ws://` reload socket. Point its
`proxy` at the apache service URL and expose its UI/port through the node
Traefik router. No TLS gymnastics if you access it over plain HTTP; if behind
HTTPS Traefik, set BrowserSync `https` + the snippet host to the `.dev.localhost`
name.

### Vite as a task-runner (classic non-ESM theme — akena model)

Vite is used as a dev-server + task runner (not a bundler): custom plugins
compile SASS, copy/concat JS, optimize images and build the SVG sprite straight
into the theme's legacy `css/ js/ images/` folders, so **`*.libraries.yml` stays
untouched**. Server block:

```js
server: {
  host: true,
  strictPort: true,
  port: 3000,
  origin: process.env.VITE_DEV_URL,          // https://<project>-vite.dev.localhost
  cors: true,
  allowedHosts: ['.dev.localhost'],
  hmr: { host: '<project>-vite.dev.localhost', protocol: 'wss', clientPort: 443 },
  watch: { usePolling: true, interval: 300 }, // Docker Desktop macOS: no inotify on bind mounts
},
```

### Vite + Tailwind CSS v4 (sterimed model)

Tailwind v4 is CSS-first — no `tailwind.config.js`/PostCSS. Entry
`src/css/tailwind.css`:

```css
@import 'tailwindcss';
@import './theme.css';        /* project partials */
@source "../../templates";     /* class-scan roots for the JIT engine */
@source "../../*.theme";
```

Two `package.json` files: **root** (build toolchain — `vite`,
`@tailwindcss/vite`, `sass` for a backend theme, prettier + tailwind plugin) and
**theme** (`web/themes/custom/<theme>` — runtime libs only). So `npm-install`
must install both:

```make
npm-install:
	$(EXEC_NODE) npm install
	$(EXEC_NODE) npm install --prefix web/themes/custom/$(THEME_FOLDER)
```

HMR served over self-signed HTTPS so it is not mixed-content behind the HTTPS
page:

```js
import basicSsl from '@vitejs/plugin-basic-ssl';
// plugins: [tailwindcss(), basicSsl(), …]
server: {
  host: true, strictPort: true, port: 3014,
  cors: true, allowedHosts: ['.dev.localhost'],
  hmr: { host: 'localhost', protocol: 'wss', clientPort: 3014 },
  watch: { usePolling: true, interval: 300 },
},
```

Drupal library swap for HMR (`<theme>.libraries.yml` + `hook_library_info_alter`):
a `hot-replacement` library loads `https://localhost:<port>/…/tailwind.css` as an
external `type: module` in dev, while the production library loads the compiled
`dist/css/tailwind.css`. Add the dev socket to the CSP: `connect-src wss://…`.

A separate CKEditor stylesheet is built with the Tailwind CLI:
`npx @tailwindcss/cli -i src/css/ckeditor.css -o dist/css/ckeditor.css` (expose as
`make npm-ckeditor` → `npm run ckeditor:watch`).

## HMR checklist (any Vite variant behind HTTPS Traefik)

1. `hmr.protocol: 'wss'` and the right `clientPort` (443 if routed via Traefik's
   websecure entrypoint; the raw dev port if accessed directly).
2. `watch.usePolling: true` (macOS Docker bind mounts don't forward inotify).
3. `allowedHosts: ['.dev.localhost']` and `cors: true`.
4. CSP `connect-src` allows the `wss://` origin.
5. The theme library URL scheme matches (`https://` not `http://`).
6. `basicSsl()` if the dev server itself must serve HTTPS.

Any one wrong → mixed-content block or a silently dead HMR socket.
