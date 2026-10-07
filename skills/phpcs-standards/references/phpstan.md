# PHPStan: set up, baseline, and clear the custom code

This is the general static-analysis pass, at whatever level the user chose.
It is not the deprecation audit: before a major core bump, run
`php-deprecations-audit` (upgrade_status + rector + phpstan deprecation rules)
instead. The two use the same `phpstan.neon`.

Run the phpcs pass first and get it clean. PHPStan fixes add docblocks, `@var`
tags and native types, so phpcs has to be run again after them (see
"Conflicts with phpcs" below).

## 1. Dependencies

On Drupal, `drupal/core-dev` already brings all of them: `phpstan/phpstan`,
`mglaman/phpstan-drupal`, `phpstan/phpstan-deprecation-rules`,
`phpstan/extension-installer`. Check `composer.json` before adding anything:

```bash
make composer c='show phpstan/phpstan mglaman/phpstan-drupal phpstan/extension-installer'
# missing, Drupal:
make composer-require mglaman/phpstan-drupal phpstan/phpstan-deprecation-rules phpstan/extension-installer --dev
# missing, plain PHP:
make composer-require phpstan/phpstan --dev
```

The extension installer has to be allowed, otherwise phpstan-drupal never
loads. You can tell because every `\Drupal::service()` comes back as `mixed`
and the error count goes up tenfold:

```json
"config": { "allow-plugins": { "phpstan/extension-installer": true } }
```

phpstan-drupal needs a real Drupal root: `web/core` must exist next to
`vendor/`. That matters in CI (see `ci-pipelines.md`).

## 2. `phpstan.neon` at the repo root

```neon
parameters:
  level: max
  paths:
    - web/modules/custom/
    - web/themes/custom/
  excludePaths:
    - */node_modules/*
  inferPrivatePropertyTypeFromConstructor: true
  reportUnmatchedIgnoredErrors: false
  ignoreErrors:
    - identifier: missingType.generics
    - identifier: missingType.iterableValue
    # Drupal render arrays and hook parameters are untyped nested arrays;
    # describing each shape with @var only to read an offset is noise.
    - identifier: offsetAccess.nonOffsetAccessible
    # new static() is a best practice in Drupal, so we cannot fix that.
    - "#^Unsafe usage of new static#"
    - '#expects string\|null, Drupal\\Core\\StringTranslation\\TranslatableMarkup given\.#'
    - '#expects string, Drupal\\Core\\StringTranslation\\TranslatableMarkup given\.#'
    - '#expects string, Drupal\\Core\\StringTranslation\\TranslatableMarkup\|string given\.#'
    - '#should return string but returns Drupal\\Core\\StringTranslation\\TranslatableMarkup\.#'
```

The `TranslatableMarkup` entries are there because Drupal's own docblocks
declare `string` where core passes markup everywhere. They are noise, not
defects.

`offsetAccess.nonOffsetAccessible` (`Cannot access offset 'x' on mixed`) is
ignored because, at level `max`, every nested read of a render array or a
hook parameter (`$items['administration']['#attached']['library']`) needs an
inline `@var array{…}` that only restates the Drupal structure. Reviewers
read those as useless comments (vitalac MR 43). The ignore only silences the
offset read itself: once the value is passed to a typed function, a
`foreach` or a method call, PHPStan still reports the `mixed`, and a `@var`
or a guard is still owed there (section 5).

**Trap: ignore patterns written for PHPStan 1.** Older templates also carry
path-scoped entries for hook files:

```neon
    - message: '#Function [a-zA-Z0-9\\_]+\(\) has no return typehint specified\.#'
      paths: [*.module, *.theme, *.install, *.inc, *.profile]
```

PHPStan 2 prints `has no return type specified` and `has parameter $x with no
type specified`, without "typehint", so these patterns match nothing. Since
`reportUnmatchedIgnoredErrors: false` is set, nothing warns you that they are
dead. Do not repair them to get the count down. Even when they match, an
untyped `$variables` stays `mixed`, and every use of `$variables['x']`
after it is reported. Typing the hook parameter is the fix (section 5). Point the dead entries out to the user and let them decide
whether to delete them.

### Which level

Ask. `max` is the agency template and is reachable on a small custom
codebase: the agena3000 theme plus three modules went from 108 errors to 0 in
one session. On a large legacy codebase, propose a lower starting level
(5 or 6) and raise it in later MRs. Never use a `phpstan-baseline.neon` to
hide the existing errors unless the user explicitly asks for one.

## 3. Makefile target

Use the same argument variable as the rest of the Makefile, which is `c` in
this pack:

```make
## phpstan: Static analysis — make phpstan [c='<args>']
phpstan:
	$(EXEC_PHP) vendor/bin/phpstan analyse --memory-limit=1G $(c)
```

If a project's existing targets take `ARGS=` instead, then `make phpstan
c='…'` silently drops the arguments. Say so, and do not mix both styles in
the same session.

## 4. Baseline

```bash
make phpstan c='--error-format=raw --no-progress'                 # one line per error, greppable
make phpstan c='--error-format=raw --no-progress' | sed 's/:.*:/ /' | sort | uniq -c | sort -rn | head
```

Group the errors by message, not by file. At level `max` on Drupal code, three
or four shapes typically account for most of the count (section 5), and each
one has a mechanical fix.

## 5. The fix catalogue

Apply one shape across all files at a time, cosmetic first, as with phpcs.
The "Runtime change" column decides whether a UAT line is owed (Step 4 of
SKILL.md).

| Error | Fix | Runtime change |
|---|---|---|
| `has parameter $variables with no type specified` / `no return type specified` on a hook | native types: `function x_preprocess_node(array &$variables): void` | none for preprocess/alter hooks, which always receive arrays |
| `Cannot access offset 'x' on mixed`, on any level of `$variables[...]`, `$form[...]`, `$attachments['#attached'][...]` | nothing: ignored in `phpstan.neon` (section 2). Do not add an `@var array{…}` only to read an offset | none |
| `mixed given` / `invalid type mixed supplied for foreach` on a value read from a nested offset | inline `/** @var array{…} $x */` or `/** @var string $x */` describing the real shape, or a guard when the shape is not guaranteed | none for `@var`; see the guard rows below |
| Same, on an array built in a loop (`$var['list'][$i]['name'] = …`) | build a local array and assign it once at the end | **yes** if the key is now set when the loop is empty, or no longer set. Keep the old behaviour (assign only when non-empty) and check the templates that read it |
| `Call to an undefined method object::getName()` after `loadTree(..., TRUE)`, `loadMultiple()`, `getTranslationFromContext()` | `/** @var \Drupal\taxonomy\TermInterface[] $tags */`, and use `getName()` / `id()` instead of `->name->value` / `->tid->value` | none: same values |
| `Cannot call method bundle() on mixed` (`routeMatch()->getParameter('node')`, `$request->attributes->get('node')`) | `if ($node instanceof NodeInterface)`, or `TranslatableInterface` when only `hasTranslation()` is needed | **yes**: a non-entity parameter used to fatal and is now skipped. Keep the original truthiness, e.g. `!$node?->hasTranslation()` becomes `!($node instanceof TranslatableInterface && $node->hasTranslation(...))` |
| `count()` / `implode()` / `explode()` on `mixed` from `$config->get()` or `$form_state->getValue()` | `is_array()` / `is_string()` guard, or `@var` when the config schema guarantees the type | **often a real bug fix**: `count(null)` throws a `TypeError` on PHP 8 when the config was never saved. UAT the "never configured" path |
| `Call to an undefined method AlterableInterface::getTables()` in `hook_query_alter()` | `if ($query instanceof SelectInterface && ...)` | none in practice: tagged queries are selects |
| `Cannot call method fetchCol() on StatementInterface\|null` | `if ($result && ...)` after `->execute()` | none |
| `parse_url()` returns `array\|false` | `is_array($parse) && ...` | none, except for malformed URLs that used to warn |
| `submitForm()` with `return parent::submitForm(...)` once typed `: void` | drop the `return`: returning a void call from a `void` function is a compile error | none |
| `?Type` return added to a function that can fall off its end (`hook_help()`) | add an explicit `return NULL;`: falling off a `?Type` function is a `TypeError` | none once the return is there. **Fatal if it is forgotten**: `php -l` does not catch it |
| Unused variable whose right-hand side is a call | delete only if the call has no side effect (`getAliasByPath()` is a pure lookup; `Node::load()` warms a cache) | see `risky-sniffs-uat.md` |
| Anything in a `.install` / update hook | `@var` annotations only: no guards, no restructuring | must be none. This code runs during the deploy, on production |

**Prefer `@var` when the runtime shape is guaranteed** (render arrays,
config with a schema, entity storage of a known type). **Prefer a guard when
it is not**: request attributes, route parameters, user input, config that
may never have been saved. A `@var` on a value that really can be `null` just
hides the bug that PHPStan found.

Do not `@phpstan-ignore` a line, and do not add an `ignoreErrors` entry for a
custom-code error, unless the user asks. If they do, the entry carries a
reason. The template's `offsetAccess.nonOffsetAccessible` entry is the agency
default, not a custom-code exception.

**Project set up before 1.3.2?** Add the entry, then remove the inline
`@var array{…}` lines that only described a shape for offset reads: drop the
class-free shapes in one pass, run PHPStan once on the whole tree, and put
back only the ones that bring an error back (typically the ones feeding a
`foreach`, `explode()` or a typed parameter). Keep any shape that types an
object (`view: \Drupal\views\ViewExecutable`). Do not run PHPStan once per
annotation.

### 5.1 Rector before the hand fixes

Rector writes the type declarations PHPStan asks for wherever it can prove
them (no `return` → `void`, a strict scalar/native/property return → that
type). It respects parent and interface signatures, so it does not break an
override. Run it once, before the catalogue above, instead of typing
functions one by one.

`rector/rector` is already there when `palantirnet/drupal-rector` was left by
`php-deprecations-audit`; otherwise:

```bash
make composer c='show rector/rector' || make composer-require rector/rector --dev
```

`rector.php` at the repo root, committed with commit 3:

```php
<?php

declare(strict_types=1);

use Rector\Config\RectorConfig;

return RectorConfig::configure()
  ->withPaths([
    __DIR__ . '/web/modules/custom',
    __DIR__ . '/web/themes/custom',
  ])
  ->withFileExtensions(['php', 'module', 'theme', 'inc', 'profile'])
  ->withAutoloadPaths([
    __DIR__ . '/web/core',
    __DIR__ . '/web/modules',
    __DIR__ . '/web/themes',
  ])
  ->withSkip([
    '*/node_modules/*',
    '*/tests/*',
  ])
  ->withTypeCoverageLevel(10);
```

`.install` is left out of `withFileExtensions` on purpose: update hooks run
on production during the deploy and get `@var` only. Adjust the paths to the
project's custom directories, as for `phpcs.xml`.

```bash
make rector c='--dry-run --no-progress-bar' | tail -30   # rules applied + files changed
make rector c='--no-progress-bar' | tail -5
make phpcbf | grep -E 'FAILED TO FIX|A TOTAL OF'      # Rector prints new code PSR-style
make phpstan c='--error-format=raw --no-progress' | sed 's/:.*:/ /' | sort | uniq -c | sort -rn | head
```

Raise `withTypeCoverageLevel()` in steps (10, 20, 30…) while the dry-run
diff stays reviewable; stop at the level where it starts adding parameter
types inferred from call sites, which can reject a value a caller outside
the custom code passes. Rector changes are type declarations only: no UAT
line unless a dry-run shows a parameter type on a hook, a public service
method or a controller, which is then reviewed and UAT'd like a guard.

## 6. Conflicts with phpcs

- `Hook implementations should not duplicate @param documentation`
  (DrupalPractice) forbids describing the parameter shape in the hook's
  docblock. When a shape is still needed (section 5), put it in an **inline**
  `/** @var ... $variables */` inside the function body instead: phpcs
  accepts it and PHPStan honours it.
- New `use` lines (`NodeInterface`, `SelectInterface`, `MarkupInterface`)
  must stay alphabetical for phpcs.
- A `@param` added to a non-hook helper needs a description line, or phpcs
  reports `Missing parameter comment`.

Re-run `make phpcs` after the PHPStan pass. Both have to be clean in the same
tree.

## 7. Prove it

```bash
make phpstan c='--no-progress'          # must end with: [OK] No errors
make phpcs                              # still: no violations
make shell
for f in $(git diff --name-only --diff-filter=ACM | grep -E '\.(php|module|inc|install|theme|profile)$'); do php -l "$f"; done
exit
make cr
```

Then follow `verification.md`. The PHPStan fixes, the Rector output,
`phpstan.neon` and `rector.php` make commit 3 (SKILL.md Step 8).
