---
name: jquery-4-migration
description: >
  Migrate a Drupal theme's JavaScript from jQuery 3 to jQuery 4 (as shipped by
  Drupal 11), on a Dockerized Makefile-driven project. Use when the user
  mentions jQuery 3→4, jQuery 4 deprecated/removed APIs ($.trim, $.isFunction,
  $.isArray, $.type, .bind/.delegate…), a jquery-deprecated / migrate polyfill,
  or "$.x is not a function" after an upgrade. Covers scanning custom + contrib
  JS, native conversions, rebuilding assets, and a scoped local polyfill for
  not-yet-compatible third-party libraries. IMPORTANT: all builds MUST go
  through Makefile/npm targets, never on the host.
---

# jQuery 3 → jQuery 4 migration (Drupal theme)

Drupal 11 ships jQuery 4. All APIs deprecated since jQuery 3.x are
**permanently removed**. Custom JS (typically under
`web/themes/custom/<theme>/src/js/`) must be migrated. This works
independently of the core bump: native replacements (`Array.isArray`,
`String.prototype.trim`, `Date.now`…) exist regardless of the jQuery version, so
you can migrate and test **while still on Drupal 10** (jQuery 3.x + polyfill).

## Golden rule: everything goes through the Makefile

Never run `npm`/`gulp` directly on the host — use the targets inside the node
container:

| Need | Make target |
|---|---|
| Build assets | `make npm-build` |
| Deploy built assets | `make gulp-deploy` |
| Clear Drupal cache | `make cr` |
| Shell in a container | `make shell` |

## The polyfill: understand before acting

Many D10 projects include a **polyfill** re-implementing removed jQuery
functions (`jquery-deprecated.js` / `polyfill.js`). Its presence means:

1. Theme code likely still depends on these APIs.
2. Two strategies:
   - **(A) Keep the polyfill** temporarily, migrate the calling code
     progressively, remove it at the end. Safest — **recommended**.
   - **(B) Migrate everything to native APIs and remove the polyfill** at once.
     Cleaner but riskier.

Start with (A); remove the polyfill once `grep` confirms zero remaining usages.

## Removed API conversion table

| Removed API | Native / jQuery 4 replacement |
|---|---|
| `$.isFunction(x)` / `$.fn.isFunction` | `typeof x === 'function'` |
| `$.type(x)` | native `typeof`, or `Array.isArray()`, `=== null`, etc. |
| `$.trim(s)` | `s.trim()` (non-null string) or `(s ?? '').trim()` |
| `$.isArray(x)` | `Array.isArray(x)` |
| `$.isWindow(x)` | `x != null && x === x.window` |
| `$.nodeName(el, n)` | `el.nodeName?.toLowerCase() === n.toLowerCase()` |
| `$.isNumeric(x)` | `!Number.isNaN(parseFloat(x)) && Number.isFinite(x)` |
| `$.now()` | `Date.now()` |
| `$.parseJSON(s)` | `JSON.parse(s)` |
| `$.unique(arr)` / `$.fn.unique` | `$.uniqueSort(arr)` |
| `$.camelCase(s)` | Internal API — replace with your own function |
| `$.fx.interval` | Removed — delete any write to this property |
| `$.cssProps.float = 'styleFloat'` | `styleFloat` no longer exists — remove |

### Other jQuery 4 changes to check

- `$.ajax`: `success`/`error`/`complete` → `.done()` / `.fail()` / `.always()` or promises.
- `.bind()` / `.unbind()` / `.delegate()` / `.undelegate()` → `.on()` / `.off()`.
- `.load()` / `.unload()` / `.error()` event shorthands → `.on('load'…)`.
- `$.isEmptyObject`, `$.proxy`: still present but watch for removal.
- `jQuery.Deferred`: behaviour aligned with native Promises.
- `hover` pseudo-events → `mouseenter` / `mouseleave`.

## Scanning custom JS

```bash
THEME_JS=web/themes/custom/*/src/js

grep -rn '\$\.isFunction\|\.isFunction(' $THEME_JS
grep -rn '\$\.trim\|jQuery\.trim' $THEME_JS
grep -rn '\$\.isArray' $THEME_JS
grep -rn '\$\.type(' $THEME_JS
grep -rn '\$\.parseJSON\|jQuery\.parseJSON' $THEME_JS
grep -rn '\$\.now\|jQuery\.now' $THEME_JS
grep -rn '\$\.isWindow' $THEME_JS
grep -rn '\$\.nodeName' $THEME_JS
grep -rn '\$\.isNumeric' $THEME_JS
grep -rn '\$\.unique\b' $THEME_JS
grep -rn '\.bind(\|\.unbind(\|\.delegate(\|\.undelegate(' $THEME_JS
grep -rn 'fx\.interval\|cssProps' $THEME_JS
```

### Scanning third-party / minified vendor — the grep blind spot

The greps above only cover readable custom source. **Minified/bundled vendor
libraries alias jQuery to a local variable** — `(function(a){… a.type(…) …})(jQuery)` —
so `$.type` / `$.isArray` etc. appear as `a.type(` / `a.isArray(` and the
`\$\.`-anchored greps **miss them entirely**. This is exactly how a removed
static like `$.type` (called by slick-carousel's `registerBreakpoints`) slips
past the scan and only surfaces at runtime.

Scan the vendor too, on the **method token alone** (and prefer each lib's
*unminified* source, where the calls are literal):

```bash
VENDOR='node_modules/slick-carousel/slick/slick.js web/themes/custom/*/js/*.min.js'
grep -oE '\.(type|isFunction|isArray|isWindow|isNumeric|trim|nodeName|parseJSON|proxy|now|unique|camelCase)\(' $VENDOR | sort | uniq -c
grep -oE '\.(bind|unbind|delegate|undelegate)\(' $VENDOR | sort | uniq -c
```

A clean `grep` is **not** proof — aliased minified calls are invisible to it.
The authoritative check is the browser (see the verification note below).

## Migration workflow — custom JS

1. Run the scan, list all affected files/lines.
2. Apply the native conversion from the table for each occurrence.
3. Rebuild: `make npm-build` then `make gulp-deploy`.
4. Test every JS interaction (modals, sliders, AJAX, forms).
5. Once `grep` shows zero usages, delete the polyfill file and its line in the
   theme's `*.libraries.yml`.
6. `make cr` and final re-test.

> **Verify in a real browser, not just grep.** Source greps cannot see aliased
> minified vendor calls, so load the site under the target jQuery (D11 core =
> jQuery 4) and watch the **console for `TypeError: … is not a function`**.
> Confirm `window.jQuery.fn.jquery` is `4.x`, that removed statics resolve
> (`typeof window.jQuery.type`), and that each plugin still initialises (e.g. a
> slider gains its `.slick-initialized` class). Zero console errors on a clean
> reload is the real pass signal.

After removing the polyfill, drop any explicit dependency on a pinned jQuery
version (let D11 core provide jQuery 4):

```bash
grep -rn 'jquery' web/themes/custom/*/*.libraries.yml
grep -rn 'core/jquery' web/themes/custom/*/
```

## Third-party & contrib libraries (in parallel)

**Custom JS is not the only source of breakage.** Third-party libraries declared
in theme `.libraries.yml` files (slick.js, lightboxes, accordions…) may also
call removed APIs. Per library: check jQuery-4 compatibility → update if
available → otherwise generate a **scoped local polyfill** (never pull in
`core/jquery.migrate`, which re-adds the entire deprecated surface). Also replace
external CDN references and any `core/modernizr` dependency (removed in D11).

**What the scoped shim contains.** For a bundled/abandoned plugin you cannot
rewrite (slick, mCustomScrollbar…), re-add *only* the removed members it
actually calls, each **guarded** (`if (typeof $.fn.bind !== 'function')`,
`if (typeof $.type !== 'function')`…) so it is a no-op under jQuery 3:

- event aliases: `.bind`/`.unbind`/`.delegate`/`.undelegate` → `.on`/`.off`
- **static helpers** (the ones the source grep misses in minified vendor):
  `$.type`, `$.isFunction`, `$.isArray`, `$.isNumeric`, `$.trim`, `$.isWindow`,
  `$.nodeName`, `$.now`, `$.parseJSON` — faithful jQuery-3 reimplementations
  (`$.type` needs the `class2type` lookup table)
- if the theme's own scripts use the **bare global `$`** (Drupal core runs
  `jQuery.noConflict()`), also restore `window.$ = window.jQuery`

Declare the shim as its own library depending on `core/jquery` **and**
`core/drupal` (so it runs *after* `noConflict()`) and load it **before** the
plugin bundle — via a `dependency`, and/or a weight that lands it after
jquery/drupal.init but before the theme bundle. Verify the actual `<script>`
order in the rendered page.

The full playbook — polyfill catalog with inter-dependencies, how to declare and
attach it in `.libraries.yml`, CDN / `core/modernizr` replacement, and the final
verification greps — is in **`references/polyfill-catalog.md`**. Load it when you
reach the third-party stage.
