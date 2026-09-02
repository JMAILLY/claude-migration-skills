---
name: php-deprecations-audit
description: >
  Audit and fix deprecated Drupal/PHP APIs in custom code before a major Drupal
  core bump, on a Dockerized Makefile-driven project. Use when the user mentions
  upgrade_status, drupal-rector, phpstan deprecation detection, "removed in D11"
  (or the next major) APIs, implicitly-nullable PHP 8.4 parameters, or fixing
  custom-code deprecations before bumping core. Runs upgrade_status + rector +
  phpstan, applies automatic + manual fixes, loops until 0 errors. IMPORTANT:
  all commands MUST go through Makefile targets; run this WHILE core is still on
  the OLD major, never after the bump.
---

# PHP & Drupal deprecations audit (before a major core bump)

> ⚠️ **RUN WHILE CORE IS STILL ON THE OLD MAJOR (e.g. Drupal 10).**
> Upgrade Status and drupal-rector derive their target from the installed core.
> On D10 they surface/fix "deprecated in D10, removed in D11" — exactly what we
> want. If core is already on D11 they switch to the D12 target and the D11
> correction list becomes unreachable. Fix everything and re-scan until 0 errors
> for the target major BEFORE bumping core.

## Golden rule: everything goes through the Makefile

Never call `drush`, `composer` or `php` directly on the host — use `make`:

| Need | Make target |
|---|---|
| Generic Drush command | `make drush c='<cmd>'` |
| Add a dev dependency | `make composer-require <pkg> --dev` |
| Static analysis | `make phpstan` |
| Coding-standards fix | `make phpcbf` |
| Shell in the PHP container | `make shell` |
| Enable a module | `make en <m>` |

For tools that must run inside the container (rector, `php -v`…), use
`make shell` and execute from within.

## Main tool: Upgrade Status

`drupal/upgrade_status` scans custom and contrib code for deprecated APIs and
next-major incompatibilities.

```bash
make composer-require drupal/upgrade_status --dev
make en upgrade_status
make drush c='upgrade_status:analyze'                 # overview
```

Report also at `/admin/reports/upgrade-status`. Target a specific module:

```bash
make drush c='upgrade_status:analyze <custom_module_name>'
make drush c='pml --type=module --status=enabled --no-core'
```

## Static analysis with PHPStan

The project has a `make phpstan` target. Ensure `phpstan.neon` includes
`web/modules/custom` and `web/themes/custom`. Recommended for deprecation
detection: `mglaman/phpstan-drupal` + `phpstan/phpstan-deprecation-rules`.

```bash
make phpstan
```

## Automate fixes: Drupal Rector

`drupal-rector` applies a large share of the corrections automatically. Its
config targets the **next** version relative to the installed core: run on D10
it prepares the code for D11 — **which is why it must run before the core bump**
(on D11 it would target D12).

```bash
make composer-require palantirnet/drupal-rector --dev
make shell
# inside the container — dry-run first:
vendor/bin/rector process web/modules/custom --dry-run
# if OK:
vendor/bin/rector process web/modules/custom
exit
```

Rector doesn't fix everything: re-run `make phpstan` and `upgrade_status`
afterwards and handle the remainder manually.

## Manual scan of custom modules

```bash
ls web/modules/custom
grep -rn 'entity.manager\|entityManager(' web/modules/custom
grep -rn 'drupal_set_message' web/modules/custom
grep -rn 'file_unmanaged_' web/modules/custom
grep -rn '\\\\Drupal::url(' web/modules/custom
grep -rn 'node_load(\|user_load(\|taxonomy_term_load(' web/modules/custom
```

## Main D11 removals table

| Removed in D11 | Replacement |
|---|---|
| `\Drupal::service('entity.manager')` | `\Drupal::entityTypeManager()` |
| `node_load()`, `user_load()` | `entityTypeManager()->getStorage(...)->load()` |
| `drupal_set_message()` | `\Drupal::messenger()->addMessage()` |
| `file_unmanaged_*` | `\Drupal\Core\File\FileSystemInterface` |
| `\Drupal::url()` | `Url::fromRoute()` / `Url::fromUri()` |
| `format_date()` | `\Drupal::service('date.formatter')->format()` |
| `drupal_render()` | `renderer` service |
| Procedural hooks | Still work but prefer PHP attribute hooks (D11) |
| `EntityManagerInterface` | `EntityTypeManagerInterface` (+ dedicated services) |

## PHP language-level deprecations (not just Drupal APIs)

Rector and Upgrade Status only target removed **Drupal** APIs — they miss pure
**PHP** deprecations tied to the new runtime (see `php-docker-upgrade`). Detect
these with `make phpstan` running under the target PHP version.

### Implicitly nullable parameters — the frequent PHP 8.4 one

> **A pure PHP 8.4 deprecation, not a Drupal API change.** Rector and Upgrade
> Status do not report it — a separate phpstan pass is required.

```php
// Before (deprecated in PHP 8.4)
public function buildForm(array $form, FormStateInterface $form_state, Request $request = null) {}

// After (correct)
public function buildForm(array $form, FormStateInterface $form_state, ?Request $request = null) {}
// or
public function buildForm(array $form, FormStateInterface $form_state, Request|null $request = null) {}
```

Rule: whenever a typed parameter has `= null` as its default, the type must be
explicitly nullable (`?Type` or `Type|null`). Frequent on `buildForm()` and
injected optional params.

**Detect:**

```bash
make phpstan 2>&1 | grep -i "implicitly"

# or grep the source directly
grep -rn "function.*\(.*[A-Z][a-zA-Z]*\s\+\$[a-z].*=\s*null" web/modules/custom/ web/themes/custom/
```

**Known contrib affected** (watch when updating): `field_group`,
`config_ignore`. They emit runtime warnings but don't block — report upstream.

## Loop until clean

Custom modules live under `web/modules/custom`. **Re-run
`upgrade_status:analyze` after each pass** until custom code is declared
compatible with the target major. Do not bump core before this reaches 0 errors.

```bash
make drush c='upgrade_status:analyze <module>'   # re-scan
```

## Cleanup at the end of the whole upgrade

The `upgrade_status` and `drupal-rector` dev dependencies are audit-only —
remove them once the core bump is done (handled by the `d11` orchestrator, not
here):

```bash
make pmu upgrade_status
make composer-remove drupal/upgrade_status
make composer-remove palantirnet/drupal-rector
```
