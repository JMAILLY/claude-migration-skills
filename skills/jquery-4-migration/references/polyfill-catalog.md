# jQuery 4 third-party libraries: scoped polyfill catalog

Handling for third-party / contrib libraries declared in theme `.libraries.yml`
files that are **not yet jQuery 4 compatible**. Do this in parallel with the
custom-JS migration, within the same step.

## 1. Inventory all declared libraries

```bash
# List all libraries declared in custom themes
cat web/themes/custom/*/*.libraries.yml

# Only those with an explicit jQuery dependency
grep -A5 "dependencies:" web/themes/custom/*/*.libraries.yml | grep -i "jquery"

# Locally bundled third-party JS files
grep -rn "\.min\.js\|vendor/" web/themes/custom/*/*.libraries.yml
```

## 2. Identify at-risk libraries

For each third-party library, check:

- Does it declare `core/jquery` or `core/jquery.ui.*`?
- Bundled locally (a `.min.js` in `vendor/`) or loaded from a CDN?
- What version — and, per the **compatibility gate** in `SKILL.md`, is a
  jQuery 4–compatible release available anywhere? Registry, git tags, releases,
  default-branch HEAD, active forks. **Never conclude from npm alone.**

```bash
# External CDN references (incompatible with Drupal CSP and jQuery 4)
grep -rn "http[s]\?://" web/themes/custom/*/*.libraries.yml
```

> ⚠️ CDN-loaded libraries (e.g. `https://cdnjs.cloudflare.com/…`) are doubly
> problematic in D11: they bypass CSP and may pin a jQuery-incompatible version.
> Replace them with a core dependency or a local file.

## 3. Strategy per library

| Situation | Action |
|---|---|
| Compatible release published on the registry | Bump the dependency, rebuild, drop the vendored copy if the build pipeline handles it |
| **Compatible release exists as a git tag only** (registry stale) | **Vendor the file from that tag** with a provenance header — see below. No shim |
| Compatible code on the default branch, untagged | Vendor it pinned to a **commit SHA**, never to a moving `master`/`main` ref |
| Only a fork is compatible | Weigh the fork's activity against rewriting the feature; vendor the fork the same way |
| No compatible version anywhere, still maintained | Scoped local `jquery.deprecated.functions.js`, and open an upstream issue |
| No compatible version anywhere, abandoned | Replace with an alternative or rewrite in vanilla JS |
| Loaded via CDN | Download locally and declare as a local asset |

A stale registry is common enough to be the default suspicion, not the
exception: publishing to npm is a manual step maintainers drop long before they
stop merging fixes.

### Vendoring a file from a git tag

Keep it **first-party**, never a `type: external` CDN URL:

- **Privacy** — a CDN sees every visitor's IP before any consent banner runs.
- **Performance** — an extra DNS + TLS handshake to a third origin, and cache
  partitioning (2020) killed the shared cross-site cache that used to justify it.
- **Aggregation** — Drupal excludes external files from CSS/JS aggregation.
- **Integrity** — a `@master` URL is mutable and a tag can be re-pushed; a
  vendored file is pinned in git and shows up in review diffs.

Before replacing a vendored file, diff it against its own upstream release: if
it comes back empty the previous copy was stock and the swap is a clean
replacement, otherwise someone patched it locally and you must port the patch.

Head every vendored file so the next person knows where it came from:

```javascript
/*
 * <library> - vendored third-party file, do not edit.
 *
 * Source:  https://github.com/<owner>/<repo> - tag <vX.Y.Z> (<short-sha>)
 * Why not npm: the <pkg> package is still frozen at <old> on the registry;
 * the <X.y> line is only published as git tags.
 * Why not a CDN: keeps the asset first-party (GDPR), aggregatable by Drupal,
 * and pinned in git.
 *
 * To upgrade: re-download <path> from the new tag and restore this header.
 */
```

Update **every** copy of the library you ship, including a minified twin that
nothing currently references — leaving a stale minified build next to an
upgraded source is a trap for whoever later switches the `.libraries.yml` to it.

Upgrading a library is not a free swap: read the upstream diff and list its
behaviour changes as manual UAT steps in the merge request. Stylesheet changes
that ship alongside can be left at the old version when they are out of scope —
say so explicitly, in the merge request and not only in the code.

## 4. Generate a scoped local polyfill

> Only reach this section once section 3's gate has been walked and written
> down. A polyfill added because nobody looked past `npm view` is pure debt: it
> outlives the reason it was written, and every library it is attached to keeps
> a dependency that reviewers can no longer justify.

When a library is not yet jQuery 4 compatible, **do not pull in
`core/jquery.migrate`** (it re-adds the entire deprecated surface and silences
every warning). Generate a small local polyfill re-implementing **only** the
removed APIs the remaining deprecated code actually calls, declare it as a
library, and attach it as a dependency of each affected library.

**Why a scoped local file rather than the migrate shim:**

- Only the APIs you genuinely still depend on stay alive — everything else stays
  truly removed, so `grep` keeps telling the truth about what's migrated.
- The file itself is the to-do list: when it's empty, you're done.
- No extra runtime dependency loaded site-wide.

First scan to find exactly which removed APIs the deprecated code (custom JS +
bundled third-party files) still calls, so the polyfill only re-implements what
is needed:

```bash
THEME=web/themes/custom/<theme>
grep -rn '\$\.isFunction\|\$\.type(\|\$\.trim\|jQuery\.trim\|\$\.isArray\|\$\.isWindow\|\$\.nodeName\|\$\.isNumeric\|\$\.now\|\$\.parseJSON\|jQuery\.parseJSON\|\$\.unique\b\|\$\.camelCase\|fx\.interval\|cssProps' \
  "$THEME/src/js" "$THEME/js"
```

### Polyfill catalog (copy only what the scan flagged)

Pick from the implementations below according to the scan results. Do not paste
the whole catalog — an unused polyfill is dead code that hides the fact the API
is no longer called. **Watch the inter-dependencies:**

- `$.type` and `$.isArray` need the shared `class2type` preamble.
- `$.isArray` calls `$.type`.
- `$.parseJSON` calls `$.trim` (include `$.trim` too).
- `$.camelCase` needs `$.fcamelCase` + the two regexes.

Shared preamble — include **only if** you copy `$.type` or `$.isArray`:

```javascript
const class2type = {};
const toString = class2type.toString;
jQuery.each(
  'Boolean Number String Function Array Date RegExp Object Error Symbol'.split(' '),
  function (i, name) {
    class2type[`[object ${name}]`] = name.toLowerCase();
  },
);
```

Individual polyfills:

```javascript
// $.isFunction / $.fn.isFunction — deprecated jQuery 3.3
$.isFunction = function (obj) { return typeof obj === 'function'; };
$.fn.isFunction = function (fn) { return typeof fn === 'function'; };

// $.type — needs the class2type preamble
$.type = function (obj) {
  if (obj == null) { return `${obj}`; }
  return typeof obj === 'object' || typeof obj === 'function'
    ? class2type[toString.call(obj)] || 'object'
    : typeof obj;
};

// $.trim — deprecated jQuery 3.5
const rtrim = /^[\s﻿\xA0]+|[\s﻿\xA0]+$/g;
$.trim = (text) => (text == null ? '' : `${text}`.replace(rtrim, ''));

// $.isArray — deprecated jQuery 3.2 — needs $.type + class2type
$.isArray = (obj) => jQuery.type(obj) === 'array';

// $.camelCase — internal API
const rmsPrefix = /^-ms-/;
const rdashAlpha = /-([\da-z])/gi;
$.fcamelCase = (all, letter) => letter.toUpperCase();
$.camelCase = (string) =>
  string.replace(rmsPrefix, 'ms-').replace(rdashAlpha, $.fcamelCase);

// $.isWindow — deprecated jQuery 3.3
$.isWindow = (obj) => obj != null && obj === obj.window;

// $.nodeName
$.nodeName = (elem, name) =>
  elem.nodeName && elem.nodeName.toLowerCase() === name.toLowerCase();

// $.isNumeric
$.isNumeric = (obj) => !Number.isNaN(parseFloat(obj)) && Number.isFinite(obj);

// $.now — deprecated jQuery 3.3
jQuery.now = function () { return new Date().getTime(); };

// $.parseJSON — deprecated jQuery 3.0 — include $.trim too
jQuery.parseJSON = function (data) {
  if (window.JSON && window.JSON.parse) {
    return window.JSON.parse(`${data}`);
  }
  return jQuery.error(`Invalid JSON: ${data}`);
};

// $.unique / $.fn.unique — deprecated jQuery 3.0, now alias of uniqueSort
if (!$.fn.unique && $.fn.uniqueSort) { $.fn.unique = $.fn.uniqueSort; }
if (!$.unique && $.uniqueSort) { $.unique = $.uniqueSort; }

// fx.interval / cssProps — only if the code writes to them
jQuery.fx.interval = 13;
jQuery.extend({
  cssProps: { float: 'styleFloat' },   // normalize float css property
});
```

Wrap the selected blocks in a single IIFE:

```javascript
/**
 * jQuery 4 deprecated-functions polyfill.
 * Re-implements ONLY the removed jQuery APIs still called by not-yet-migrated
 * third-party / contrib libraries.
 * TODO: remove once every dependent library is jQuery 4 compatible and `grep`
 * confirms zero usages.
 */
(function ($) {
  // … only the catalog blocks the scan flagged …
})(jQuery);
```

Save it at `web/themes/custom/<theme>/js/jquery.deprecated.functions.js`.

## 5. Declare and attach the polyfill

```yaml
# web/themes/custom/maintheme/maintheme.libraries.yml

# Temporary polyfill for jQuery APIs removed in jQuery 4.
# TODO: remove once all dependent libraries are jQuery 4 compatible.
jquery-deprecated-functions:
  js:
    js/jquery.deprecated.functions.js: {}
  dependencies:
    - core/jquery

my-slider:
  js:
    js/vendor/slick.min.js: {}
  dependencies:
    - core/jquery
    - maintheme/jquery-deprecated-functions   # TODO: remove when slick is jQuery 4 compatible

my-lightbox:
  js:
    js/vendor/fancybox.min.js: {}
  dependencies:
    - core/jquery
    - maintheme/jquery-deprecated-functions   # TODO: remove when fancybox 5.x is available
```

> The polyfill is a safety net — not a permanent solution. Scope it to the exact
> APIs still called, keep the `TODO`, and delete the file (and the dependency
> lines) once every dependent library is migrated and `grep` confirms zero usages.

## 6. Replace CDN jQuery UI / core/modernizr dependencies

In D11, `core/modernizr` is removed. jQuery UI references loaded from an external
CDN must be replaced by the `drupal/jquery_ui_*` contrib modules:

```bash
grep -rn "modernizr\|jquery-ui\|jqueryui" web/themes/custom/*/*.libraries.yml
```

```yaml
# Before (D10 — external CDN, incompatible with D11)
accordion-init:
  js:
    https://cdnjs.cloudflare.com/ajax/libs/jqueryui/1.14.1/jquery-ui.min.js: { type: external }
  dependencies:
    - core/modernizr

# After (D11 — core/contrib dependencies)
accordion-init:
  dependencies:
    - core/jquery.ui.accordion   # or drupal/jquery_ui_accordion depending on the installed module
```

## 7. Final `.libraries.yml` verification

```bash
# No remaining external references
grep -rn "http[s]\?://" web/themes/custom/*/*.libraries.yml

# No remaining modernizr references
grep -rn "modernizr" web/themes/custom/*/*.libraries.yml

# No leftover core/jquery.migrate (we use a scoped local polyfill instead)
grep -rn "jquery.migrate" web/themes/custom/*/*.libraries.yml

# Libraries still depending on the temporary polyfill (to handle progressively)
grep -rn "jquery-deprecated-functions" web/themes/custom/*/*.libraries.yml
```
