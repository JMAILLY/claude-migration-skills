---
name: drupal-scaffold
description: >
  Hand a Drupal project's scaffold files (web/.htaccess, index.php, robots.txt,
  default.settings.php, README/example files…) back to
  drupal/core-composer-scaffold on a Dockerized, Makefile-driven project: untrack
  and gitignore every generated file, move project customizations into
  scaffold/*-prepend.txt / *-append.txt (or a full replacement), make
  branch-specific .htaccess edits (prod redirects, firewall, force-www, preprod
  Basic auth) safe on every environment, and add a preprod-auth GitLab CI job
  when the preprod needs a password. Use when the user mentions
  drupal-scaffold, file-mapping, "[web-root]/.htaccess": false, a hand-edited
  .htaccess that conflicts or silently changes between develop / release /
  master, prod redirects in .htaccess, a committed .htpasswd, or preprod Basic
  auth. IMPORTANT: all commands MUST go through Makefile targets; check what the
  CI and deploy read before untracking anything.
---

# Drupal scaffold files under composer control

`drupal/core-composer-scaffold` writes ~20 files from core
(`web/core/composer.json` → `extra.drupal-scaffold.file-mapping`). Projects
usually freeze some of them with `false` and hand-edit them per branch. Symptoms:

- `.htaccess` differs on every long-lived branch (prod redirects on `master`,
  Basic auth on `release`). A merge between them often **does not conflict**:
  when only one side changed the file since the merge base, git silently takes
  that side. Preprod auth lands in `develop`, then in prod.
- Frozen files stay on the previous core's version after a major bump.
- A `.htpasswd` is committed with the preprod credentials.

Target state: every scaffold output is generated and untracked. Project-specific
content lives in `scaffold/` and is identical on every branch. Environment-only
behaviour sits behind a host condition, or in CI.

## Golden rule: everything goes through the Makefile

| Need | Make target |
|---|---|
| Regenerate the scaffold files | `make composer c='drupal:scaffold'` |
| Refresh `content-hash` after editing `extra` | `make composer c='update --lock'` |
| Validate | `make composer c='validate --no-check-publish'` |
| Smoke tests | `make cr`, `make drush c='…'` |

## 0. Ask once

- The long-lived branches and the environment each one deploys (e.g.
  `develop` → none, `release` → preprod, `master` → prod).
- Whether the preprod must be password-protected (→ step 6).
- The ticket, and whether `gm:merge-request` is available for the MR.

## 1. Inventory

```bash
# Every file core scaffolds, and where to.
python3 -c "import json;m=json.load(open('web/core/composer.json'))['extra']['drupal-scaffold']['file-mapping'];print('\n'.join(m))"
# Project overrides: locations, file-mapping, gitignore, initial.
python3 -c "import json;print(json.dumps(json.load(open('composer.json'))['extra']['drupal-scaffold'],indent=2))"
git ls-files web/.htaccess web/index.php web/update.php web/robots.txt web/.ht.router.php \
  web/sites/default/default.settings.php web/sites/default/default.services.yml \
  web/sites/*.php web/sites/*.yml web/sites/README.txt web/*.txt web/*.md \
  web/.csslintrc web/.eslint* web/example.gitignore web/*/README.txt recipes/README.txt \
  .editorconfig .gitattributes
git ls-files | grep -E '(^|/)\.htpasswd$'
```

Read the root `.gitignore` too. Template-era entries such as `/.htaccess` or
`/index.php` with no `web/` prefix ignore nothing when the web root is `web/`.

## 2. Classify every tracked scaffold file, on every long-lived branch

Diff each branch's copy against the **stock file of that branch's core version**.
Otherwise the core diff (D10 → D11 stock) hides the project's changes:

```bash
S=<session scratchpad dir>
for b in origin/develop origin/release origin/master; do
  v=$(git show "$b:composer.lock" | python3 -c "import json,sys;print(next(p['version'] for p in json.load(sys.stdin)['packages'] if p['name']=='drupal/core'))")
  curl -s "https://git.drupalcode.org/project/drupal/-/raw/$v/core/assets/scaffold/files/htaccess" > "$S/htaccess.$v"
  git show "$b:web/.htaccess" | diff "$S/htaccess.$v" - > "$S/htaccess.${b#origin/}.diff"
done
```

(Repeat for each tracked file; the stock
name is the right-hand side of core's `file-mapping`.)

| Delta vs stock | Mapping | Git |
|---|---|---|
| none | remove the override | untrack |
| additions at the top or bottom, or whose position does not matter | `{"prepend": "scaffold/<name>-prepend.txt"}` / `"append"` | untrack |
| the file is entirely the project's (custom `robots.txt`) | `"scaffold/robots.txt"` (full replacement) | untrack |
| edits in the middle of a stock file that must stay where they are | keep `false`, last resort | keep tracked |
| present on one branch only (env-specific) | make it safe everywhere (host condition) or move it to CI (step 6) | — |

`.htaccess` customizations almost always fit a prepend once you know which
directives are position-independent: see `references/htaccess.md`. Drop the
lines that only duplicate stock rules; the reference lists the dangerous ones.

Do not port `default.settings.php` changes. Projects put real settings in
`settings.php` or an included file; stock comment blocks are core's job.

## 3. composer.json

```json
"drupal-scaffold": {
    "locations": { "web-root": "web/" },
    "gitignore": false,
    "file-mapping": {
        "[web-root]/.htaccess": { "prepend": "scaffold/htaccess-prepend.txt" },
        "[web-root]/robots.txt": "scaffold/robots.txt"
    }
}
```

- `scaffold/` sits at the project root, outside the web root, so it is never
  served. It must be shipped with the code: check the deploy rsync excludes.
- `"gitignore": false`: otherwise the plugin, once `vendor` is ignored, writes a
  `.gitignore` into each destination directory. One explicit root block is
  easier to review.
- `extra` is part of `content-hash`: run `make composer c='update --lock'`, then
  `make composer c='drupal:scaffold'`.

Verify each generated file is exactly the parts in order (the plugin adds a
newline between the parts):

```bash
{ cat scaffold/htaccess-prepend.txt; echo; cat web/core/assets/scaffold/files/htaccess; } | diff - web/.htaccess && echo OK
```

## 4. Untrack and ignore

```bash
git rm --cached <every scaffold output>          # local files stay
```

```gitignore
# Drupal scaffold output
/web/.htaccess
/web/index.php
…one line per destination from step 1…
/web/.htpasswd
```

Keep the root `.editorconfig` / `.gitattributes` tracked if the project lists
them under `initial`: the plugin writes those once and never overwrites them.

## 5. Prove the build chain regenerates them

Untracked outputs must be rebuilt wherever code is packaged:

- `composer install --no-scripts` **still scaffolds**. The scaffold is a plugin
  listener, and Composer only skips script listeners
  (`EventDispatcher::getListeners`: `$this->runScripts ? getScriptListeners() : []`).
- **Split CI jobs**: if the composer job's `artifacts:paths` lists only
  `vendor/` and `web/core/`, later jobs see no scaffold output. Add the
  destinations, or the deploy uploads a tree with no `index.php`.
- **Grep CI and deploy for scaffold paths**:
  `grep -nE 'default\.settings|htaccess|index\.php|robots' .gitlab-ci.yml deploy*.php`.
  A classic case is a `settings` job that runs `cp default.settings.php settings.php`
  and depends on the composer job's artifacts.
- **The server**: when the deploy recipe runs `composer install` there,
  generation happens on the server too. When it only rsyncs, the CI artifacts
  are all it gets.

Local proof: `rm web/.htaccess web/index.php && make composer c='install'`, and
both files come back.

## 6. Preprod Basic auth: a CI job, not a branch-only .htaccess

When the preprod must be password-protected:

- Add the `preprod-auth` job from `references/htaccess.md` § Preprod auth. It
  runs in the `deploy` stage, on the preprod branch only, with `needs: [deploy]`.
  It writes `.htpasswd` from a masked CI variable and appends the auth block to
  the deployed `.htaccess`.
- Untrack any committed `.htpasswd` and ignore it. **Rotate the password**: the
  hash stays in the history.
- MR prerequisite: create the CI variable (e.g. `PREPROD_HTPASSWD`) before the
  next preprod deploy. Without it the job writes an empty `.htpasswd` and locks
  everyone out.

## 7. Merging long-lived branches

Before resolving a `develop` ← `release` / `master` merge, list the files that
merge **without** conflict but change:

```bash
git merge --no-commit --no-ff origin/release
git diff --cached --stat HEAD     # an .htaccess here = env-specific content arriving
```

`git merge-tree --name-only` only lists conflicts, so it misses these.

## 8. Verify

On the local stack (Apache reads the generated `web/.htaccess`):

```bash
B=https://<project>.dev.localhost
for u in / /<a-redirected-path> /<path>/ "/?q=union+select+(1)" /.git/config /composer.json; do
  curl -sk -o /dev/null -w "$u %{http_code} %{redirect_url}\n" "$B$u"; done
```

Expected: front and back office 200, each 301 to its target, trailing slash
301, firewall 403, `/.git/config` and `/composer.json` 403.

Host-specific rules (force-www on the prod domain) cannot be tested through
Traefik, which routes by `Host` and answers 404 for an unknown host. Hit Apache
directly:

```bash
docker compose … exec -T apache sh -c 'printf "GET /foo HTTP/1.0\r\nHost: example.com\r\n\r\n" | nc -w3 localhost 80 | grep -E "^HTTP|^Location"'
```

A 400 for any other host is Drupal's `trusted_host_patterns`, not a redirect.

## 9. Close

One commit for the mapping + `scaffold/` + untracking, one for the preprod
auth if any, on the ticket's branch, and a Draft MR. The MR body states:

- **Prerequisites**: the CI variable, the password rotation.
- **Behaviour changes in prod**: dropped duplicate rules, the force-www host
  restriction.
- **Production actions**: none to run (the deploy's `composer install`
  regenerates). After delivery, check the www redirect, a few 301s and the back
  office.

Any later hand edit of `web/.htaccess` (e.g. the `node_modules` deny rule from
`gulp-to-vite`) goes into `scaffold/htaccess-prepend.txt`. The next scaffold run
overwrites the generated file.
