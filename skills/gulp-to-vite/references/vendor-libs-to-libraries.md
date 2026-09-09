# Follow-up: concat manifest → `*.libraries.yml` (vendor libs from `node_modules`)

Some legacy Gulp themes do **not** copy JS per file: they concatenate an ordered
list of vendor libraries plus the theme's own scripts into a single
`script.min.js`. The list lives in a manifest at the repo root — `site.json` on
agena3000:

```json
{
  "jsFiles": [
    "./node_modules/jquery/dist/jquery.min.js",
    "./node_modules/svgxuse/svgxuse.min.js",
    "./node_modules/slick-carousel/slick/slick.min.js",
    "./node_modules/masonry-layout/dist/masonry.pkgd.min.js",
    "./node_modules/scrollreveal/dist/scrollreveal.min.js",
    "./node_modules/leaflet/dist/leaflet.js",
    "./web/themes/custom/<theme>/src/js/*.js"
  ]
}
```

This document covers **replacing that manifest** with real `*.libraries.yml`
entries served out of the theme's own `node_modules` — the sterimed pattern
(`node_modules/swiper/swiper-bundle.js` &c. in `frontend.libraries.yml`).

> **Do NOT do this during the iso-functional Gulp→Vite migration.** It changes
> how assets load, so it needs its own branch, its own MR and its own UAT. And
> schedule it **with the jQuery 4 step, not after** — the jQuery-4 audit decides
> which vendor libraries survive, and repackaging a library you then have to
> patch or replace is wasted work. (On agena3000, `slick-carousel@1.8.1` calls
> the removed `$.type()` five times.)

During the iso-functional migration, keep the concat and make the plugin read
the manifest, with a fallback so deleting it later is a no-op:

```js
// plugins/vite-concat-js.js — resolveSources()
let patterns = [fallbackGlob];                 // <theme>/src/js/*.js
try {
  const parsed = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
  if (Array.isArray(parsed.jsFiles) && parsed.jsFiles.length) patterns = parsed.jsFiles;
} catch { /* no manifest: fall back to the theme's own scripts */ }
```

---

## 1. The theme needs its own `package.json`

`*.libraries.yml` paths resolve **relative to the defining extension**, so
`node_modules/foo/bar.js` means `web/themes/custom/<theme>/node_modules/foo/bar.js`.
The repo-root `node_modules` is unreachable. Hence two npm projects: root holds
the build tooling, theme holds the runtime libraries.

```json
{
  "name": "<theme>",
  "version": "1.0.0",
  "private": true,
  "description": "Runtime libraries served directly from node_modules by <theme>.libraries.yml",
  "dependencies": {
    "leaflet": "^1.5.1",
    "masonry-layout": "^4.2.2",
    "scrollreveal": "4.0.7",
    "slick-carousel": "^1.8.1",
    "svgxuse": "^1.2.6"
  }
}
```

Remove those same packages from the root `package.json`. **Commit the theme's
`package-lock.json`** — CI runs `npm ci --prefix`, which fails without it.

## 2. `*.libraries.yml`: weights reproduce the concat order

Within one library, load order comes from `weight`, *not* YAML order. Give the
vendor files weights **below** the theme script's existing weight so the
sequence matches what concatenation used to guarantee:

```yaml
global-styling:
  version: "1.0"
  css:
    theme:
      css/style.css: {}
  js:
    node_modules/svgxuse/svgxuse.min.js: { minified: true, weight: -10 }
    node_modules/slick-carousel/slick/slick.min.js: { minified: true, weight: -9 }
    node_modules/masonry-layout/dist/masonry.pkgd.min.js: { minified: true, weight: -8 }
    node_modules/scrollreveal/dist/scrollreveal.min.js: { minified: true, weight: -7 }
    node_modules/leaflet/dist/leaflet.js: { minified: true, weight: -6 }
    js/script.min.js: { weight: -5 }       # keep its existing weight
  dependencies:
    - core/jquery
```

Set `minified: true` on files that are already minified so Drupal does not
re-process them. Check what each package actually ships: Leaflet's
`dist/leaflet.js` **is** the minified build (`leaflet-src.js` is the readable
one), and there is no `leaflet.min.js`.

Verify against the **served HTML**, not the YAML:

```bash
curl -sS https://<project>.dev.localhost/ \
  | grep -oE 'src="[^"]*(jquery|swiper|slick|masonry|scrollreveal|leaflet|script\.min)[^"]*"'
```

## 3. The jQuery trap — read this before deleting the bundled jQuery

Dropping the theme's own jQuery in favour of `core/jquery` looks like a pure win
(it removes a genuine double-load). **It will break every bare `$` call in the
theme.** Drupal core runs `jQuery.noConflict()` in `core/misc/drupal.init.js`,
which *deletes* `window.$`. The bundled copy, concatenated at the top of
`script.min.js`, used to re-create `window.$` **after** noConflict had already
run. That side effect was load-bearing, not a bug.

Symptom: `Uncaught TypeError: $ is not a function` at the first line of
`script.min.js`.

The fix is the idiomatic Drupal wrapper:

```js
(function ($) {
  // …the entire existing file…
})(jQuery);
```

**Run these three checks first** — the wrapper also scopes every top-level
`var`/`function`, so anything reaching them by name from outside will break:

```bash
T=web/themes/custom/<theme>
grep -rhoE 'on(click|change|submit|load|input|blur|focus)=' $T/templates | wc -l   # inline handlers
grep -rho '\$('  $T/templates | wc -l                                             # $ in Twig <script>
grep -c '\$('    $T/tarteaucitron/tarteaucitron.js                                # other bundled libs
```

All three must be `0`. If they are not, either keep a global alias
(`window.$ = window.jQuery;` in a tiny shim loaded before the theme script —
behaviour-preserving but perpetuates the anti-pattern) or convert the offending
call sites.

A welcome side effect once wrapped: esbuild can finally mangle the top-level
names, because they are no longer in script scope.

While you are here, grep for `$('document').ready(` — a string selector for a
non-existent `document` element. It works in jQuery 3 but `.ready()` on a
collection is **removed in jQuery 4**, so it belongs to that step.

## 4. Deployment: one character

A theme's `node_modules` must now reach the server. The usual rsync exclusion is
**unanchored**, so it silently skips the theme's copy too and every library
404s in production:

```php
// deploy.php — upload_options
'--exclude=node_modules',    // WRONG: matches at any depth
'--exclude=/node_modules',   // RIGHT: only the repo-root build tooling
```

Prove it rather than trusting the semantics — and note `rsync -an` prints
nothing without `-v`:

```bash
rsync -avn --exclude=/node_modules --exclude=/vendor --exclude=/web/core ./ /tmp/rt/ \
  | grep -c '^web/themes/custom/<theme>/node_modules/'   # want: >0
rsync -avn --exclude=node_modules  --exclude=/vendor --exclude=/web/core ./ /tmp/rt/ \
  | grep -c '^web/themes/custom/<theme>/node_modules/'   # want: 0 (the bug)
```

## 5. CI and Makefile

```yaml
# .gitlab-ci.yml — the npm preparation job
script:
  - npm ci
  - npm ci --prefix web/themes/custom/<theme>
artifacts:
  paths:
    - node_modules/
    - web/themes/custom/<theme>/node_modules/     # must reach the deploy stage
```

Add the same path to the **build job's** artifacts, otherwise the deploy stage
never sees it. Keep the css/js/images artifact paths unchanged.

```make
THEME_FOLDER := $(shell grep -E '^THEME_FOLDER=' .env 2>/dev/null | cut -d= -f2)
THEME_DIR    := web/themes/custom/$(or $(THEME_FOLDER),<theme>)

npm-install:
	$(EXEC_NODE) npm install
	$(EXEC_NODE) npm install --prefix $(THEME_DIR)
```

Make `init` call `npm-install` rather than a bare `npm install`, or a fresh
clone 404s every library.

## 6. `node_modules` is now inside the docroot

Two consequences, both real.

**Never commit it.** The usual root-anchored rule does not cover it:

```gitignore
/node_modules/
/web/themes/custom/*/node_modules/
```

(sterimed only has the first line, so its theme `node_modules` shows up as
untracked noise in every `git status` — do better.)

**npm metadata becomes publicly readable.** Measured on agena3000: `package.json`,
`README.markdown` and `.map` files all answered **200**. No secrets, but it lets
anyone enumerate exact library versions to match against known CVEs. Drupal's
`.htaccess` blocks `composer.json`, not `package.json`. Add:

```apache
# web/.htaccess, inside the RewriteEngine block
RewriteRule ^themes/custom/[^/]+/node_modules/.*\.(json|md|markdown|txt|ts|map|lock|yml|yaml)$ - [F,L]
```

Residual: unminified `.js` sources (e.g. `leaflet-src.js`) still serve. Same
public OSS code, so this is usually accepted rather than chased.

## 7. Verification

```bash
T=web/themes/custom/<theme>
# every declared path exists on disk
grep -oE "^\s+(css/|js/|node_modules/)[^:]+" $T/<theme>.libraries.yml | tr -d ' ' | sort -u |
  while read -r p; do [ -f "$T/$p" ] && echo "OK $p" || echo "MISSING $p"; done

make cr        # library definitions are cached; without this nothing changes

# each asset answers 200, and exactly ONE jQuery is loaded
curl -sS https://<project>.dev.localhost/ | grep -coE 'src="[^"]*jquery[^"]*"'   # want 1
# metadata is denied
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://<project>.dev.localhost/themes/custom/<theme>/node_modules/leaflet/package.json  # want 403
```

Then in a browser: the carousels, the masonry grid, the scroll animations, the
map and the SVG sprite — i.e. one behaviour per library you just moved. A
`$ is not a function` in the console means §3.

## 8. Expect these, and say so

- **Weight on the wire.** agena3000 ships **8.1 MB / 511 files** for five
  libraries, **3.2 MB of it a jQuery pulled in transitively by slick and never
  served**. Reducible (move it to the theme's `devDependencies`, or `.npmrc`),
  but it is not free out of the box.
- **One request per library instead of one bundle.** Drupal's aggregation is on
  in production, so this is not the regression it looks like.
- **The theme's `package-lock.json` is a new tracked file**, and `npm ci
  --prefix` depends on it.
