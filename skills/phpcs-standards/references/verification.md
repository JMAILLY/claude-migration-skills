# Verifying a standards pass on a codebase with no tests

Custom Drupal modules usually ship no test coverage, so a branch that injected
dependencies and renamed methods cannot be validated by a suite. It is
validated empirically, in this order. Everything runs through the Makefile.

## 1. The container still compiles

```bash
make cr
```

Catches: a bad `*.services.yml`, an argument count mismatch, a missing service
id, a circular reference. Run it after **every** module that had a risky fix,
not once at the end — otherwise the failure has ten possible causes.

## 2. Every declared service instantiates

For each `*.services.yml` under the custom modules path:

```bash
make drush c="php:eval '
foreach ([\"module.service_a\", \"module.service_b\"] as \$id) {
  if (!\Drupal::hasService(\$id)) { print \"MISSING \$id\n\"; continue; }
  try { \Drupal::service(\$id); print \"OK \$id\n\"; }
  catch (\Throwable \$e) { print \"FAIL \$id — \" . \$e->getMessage() . \"\n\"; }
}'"
```

Build the id list from the YAML files rather than by hand, and print one line
per service so the output is diffable between runs.

## 3. Controllers and forms build from the container

Instantiation of the *service* passes even when a controller's `create()` was
left pulling the wrong argument. For every `_controller` and `_form` in the
custom `*.routing.yml`:

```php
Cls::create(\Drupal::getContainer());
```

## 4. Plugins instantiate

`createInstance()` every custom block, action, field formatter and Views
handler.

> **Plugin ids rarely match class names.** A class `VisitTourBlock` can be
> `block-visit-tour`, `NouveauteSearch` can be `new_products_research`. Read the
> id from the `@Block` annotation / `#[Block]` attribute — guessing makes a
> healthy plugin look broken, and a broken one look absent.

## 5. One real read per refactored service

Instantiation proves wiring, not correctness: a service handed the wrong
storage handler constructs perfectly and returns nothing. So exercise one
actual call per refactored service against the live database and compare the
count to what the same call returned **before** the branch:

```bash
git stash && make drush c="php:eval '...'"   # baseline
git stash pop && make drush c="php:eval '...'"   # after
```

## 6. Syntax, including the modules the container cannot see

Modules absent from `config/sync/core.extension.yml` are **not installed and not
autoloadable** — `\Drupal::service()` will never find their services, and that
is not a regression. They can only be checked statically:

```bash
make shell
php -l web/modules/custom/<uninstalled_module>/src/Foo.php
exit
make phpcs c='web/modules/custom/<uninstalled_module>'
```

List those modules explicitly in the MR under `## Hors-scope`, so the reviewer
knows why they were not exercised.

## 7. Config that references code

Renaming a public method or a plugin id can invalidate exported config. Before
committing a rename:

```bash
grep -rn '<oldName>' config/sync/ web/ --include='*.yml' --include='*.php' \
  --include='*.twig' --include='*.module' --include='*.theme'
```

And after: `make cim` must report no unexpected change, and `make cex` must
produce an empty diff.

## What goes in the MR

Under `## Vérification`, only what actually ran, with its result:

```markdown
## Vérification
- ✅ `make phpcs` : 0 violation (Drupal + DrupalPractice, erreurs et warnings) — 1375 avant
- ✅ `php -l` sur les 87 fichiers modifiés
- ✅ `make cr` : conteneur recompilé
- ✅ 23/23 services instanciés, 11 contrôleurs et formulaires via `::create()`
- ✅ `SearchService::getData('article')` → 1123 lignes (identique à `develop`)
```

Never write a check that did not run.
