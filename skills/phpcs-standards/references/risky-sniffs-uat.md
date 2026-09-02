# Sniffs that change behaviour → the UAT they demand

A coding-standards pass is assumed to be cosmetic. On Drupal it is not: the
`DrupalPractice` family and the naming sniffs rewrite how objects are built and
what methods are called. Everything below has broken a real site.

**Rule: one risky category, in one module, = one commit + one UAT line in the
MR.** Never fold a risky fix into a `style(...)` commit.

## The catalogue

| Sniff / fix | What really changes | Can break | UAT to write (French, concrete) |
|---|---|---|---|
| `DrupalPractice.Objects.GlobalDrupal` / `GlobalClass` → constructor injection | the service is constructed by the container instead of pulling `\Drupal::` at call time | container compile, `*.services.yml` argument order, plugin `create()`, a service that was lazily resolved now resolved at build | « <parcours qui utilise le service> → <résultat attendu chiffré> » |
| `DrupalPractice.Objects.GlobalFunction` — `t()` inside a class → `$this->t()` + `StringTranslationTrait` | the string goes through the translation service; forgetting the trait or the `use` is a **fatal**, not a warning | any label, message, form title, block content in the module | « <formulaire/bloc> s'affiche en français, libellés corrects » |
| `Drupal.NamingConventions.ValidFunctionName` — method renamed to lowerCamel | **public API break** | callers in other modules, `_controller:`/`_form:` in `*.routing.yml`, `callback:` / `factory:` in `*.services.yml`, `hook_theme` callbacks, Views handlers, Twig calls, and **exported config in `config/sync/`** | grep the whole repo *and* `config/sync/` for the old name first; then « la route <path> répond 200 et affiche <x> » |
| `Drupal.Files.LineLength` on a docblock carrying a plugin annotation (`@Block`, `@FieldFormatter`, `@Action`…) | the annotation is **parsed from the docblock** — a wrapped `id =` or `admin_label =` line changes or destroys the plugin definition | plugin discovery: the block disappears from the layout, the action from the bulk-operations list | `make cr`, then « le bloc <label> est toujours placé sur <page> » |
| Long-line wrapping inside a string concatenation, a query builder chain or a Twig-bound string | a space can appear/disappear in rendered output or in SQL | rendered labels, exported CSV headers, `LIKE` patterns | « <page/export> affiche exactement <chaîne attendue> » |
| Removing an "unused" variable or an "unread" assignment | the removed call may have had a **side effect** — `Node::load()` warming a cache, a setter, a `->execute()` whose return nobody read | anything downstream of that side effect | « <flux complet> se termine et <effet attendu> est visible » |
| Removing an "unused" loop key (`foreach ($x as $k => $v)` → `as $v`) | harmless — *unless* `$k` was used inside a closure or a string | rare | diff review is enough |
| `t()` placeholder normalisation (`@`, `%`, `:`) | a wrong prefix renders the literal `@name` instead of the value, or unescapes user input (**XSS**) | every message touched | « le message affiche la vraie valeur, pas `@variable` » |
| Autofixes inside a `.theme` / `*.module` preprocess function | template variables and their types | every template consuming those variables | « une page de chaque type de contenu/paragraphe modifié s'affiche sans erreur » |
| `Drupal.Commenting.*` deleting a `@param`/`@return` block | nothing at runtime — **unless** it removed an attribute or annotation line above it | plugin/route discovery | diff review + `make cr` |
| Reordering `use` statements / removing an "unused" one | a `use` can be needed by a docblock-typed annotation or a string class reference | class resolution | `php -l` + `make cr` |
| Renaming a snake_case property/variable that is a **render array key** or a **form state key** | keys are contractual | the form or the render array | « le formulaire se soumet et enregistre » |

## Writing the UAT line

Bad: « vérifier que la recherche fonctionne ».
Good: « /recherche?type=article → 1123 résultats, facette "Récents" active ».

An entry is complete when someone who did not write the code can execute it
without asking a question:

1. the URL or the admin path,
2. the action,
3. the expected result, with a number or an exact string when one exists,
4. the account/role needed if it is not anonymous.

If a fix touches something you cannot express that way — you do not know what
the code is for — that is a signal to **stop and ask the user** rather than to
write a vague line.

## Categories that need no UAT

Diff review is enough for: whitespace, indentation, blank lines, missing full
stops in comments, docblock formatting that adds no annotation, file-end
newlines, `array()` → `[]`, `elseif` spelling, comparison spacing.

Everything else earns a line.
