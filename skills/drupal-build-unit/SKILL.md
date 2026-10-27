---
name: drupal-build-unit
description: >
  Build one unit of a Drupal site build (drupal-build) — a header, a footer,
  a recurring element, a media type or shared editing feature, one paragraph
  type, one taxonomy, one content type or one third-party integration —
  through a fixed loop: CDC scoping by REQ, targeted Figma confrontation by
  node id per breakpoint and state, gaps arbitrated for the CDC, a brief and
  action plan (acceptance criteria tied to REQs, data model, files,
  accessibility by design, demo content, test strategy) validated unless in
  auto mode, a build/<id> branch, implementation with gm:drupal and the
  starter's conventions, self-verification (phpcs, phpstan, build, PHPUnit,
  Playwright E2E + axe + visual regression on every delivered unit, config
  idempotence, logs, visual comparison with Figma in Chrome), then
  drupal-rgaa and gm:review, and delivery (Playwright captures uploaded to
  GitLab, French local UAT, Draft MR, .build/ update). Loads the reference of
  its category. One unit per conversation. Use when the drupal-build
  orchestrator routes here. IMPORTANT: CDC wins over Figma; read only the
  unit brief and the Contracts of its dependencies; all commands MUST go
  through Makefile targets; never merge, never write content on preprod/prod.
---

# Build one unit

Part of the `drupal-build` campaign. One unit, one branch, one Draft MR, one
conversation. The category reference says what the unit must deliver and
check: `references/categories/<category>.md` (`header`, `footer`,
`recurring`, `media`, `paragraph-block`, `taxonomy`, `content-type`,
`integration`). With `sites:` in `state.md`, also
`../drupal-build/references/multisite.md`.

Shared references, in `../drupal-build/references/` (relative to this skill's
directory): `build-memory.md`, `demo-content.md`, `testing.md`,
`screenshots.md`; and `../drupal-build-foundations/references/design-tokens.md`
for the token rules.

**No subagents.** When the context grows, write the state to `.build/`,
commit, and resume after `/clear`.

## Load only this

```bash
cat .build/state.md
cat .build/units/<id>.md
head -4 .build/requirements.md; grep -E '\| <id> +\|' .build/requirements.md
sed -n '/^## Contract/,$p' .build/units/<dependency>.md     # each dependency, foundations included
grep -E '^## D-' .build/decisions.md                         # then only the relevant entries
```

Then the category reference. Nothing else: not the full CDC, not a Figma
page, not a dependency's code. When the brief names a **source bundle** (a
block ported from the source site in `state.md`), read only that bundle's
files there: its config, template, preprocess and CSS. A Contract that does not answer a question is
**completed** (in its own file, mentioned in this MR), not bypassed by
reading code.

If the branch `build/<id>` already exists, this is a resume: switch to it,
read its commits and the brief's Plan, and continue at the first unfinished
step.

## 1. CDC scoping

List the REQs of the unit with their condensed text. A doubt about one opens
**only** the CDC page cited in its `Source`. The CDC wins over everything.

## 2. Figma confrontation

Load **`figma:figma-design-to-code`**. For each row of the brief's Figma
nodes table: `get_design_context` and `get_screenshot` **on that node id
only**, per breakpoint and per state (hover, focus, open, empty, error, long
content). Check the behaviour too (what opens, what moves, what happens with
no item), not just the rendering. Map every value to a foundations token;
note the ones that have none.

## 3. Gaps

Arbitrated in favour of the CDC, written in the brief's « Gaps and
decisions » (project-wide ones in `decisions.md`).

- **Not drawn** (a breakpoint, a state): no question — build the simplest
  functional version on the foundations (grid, spacing, components), and
  write one line in the brief saying what was derived. Ask only when the CDC
  imposes a behaviour the simple version would miss.
- **Blocking ambiguity**: a question, never a silent assumption.

## 4. Brief and action plan

Written in the brief's Plan section, presented in French, in the shape of a
`/gm:ticket` brief without a ticket:

- **Objectif** — one or two sentences.
- **Critères d'acceptation** — numbered, each tied to its REQ; deduced ones
  marked « (inféré) ».
- **Modèle de données** — bundles, fields (machine name, type, cardinality,
  required), widgets, formatters, view modes, translatability (asymmetric
  paragraphs when multilingual).
- **Fichiers concernés** — config, templates, `includes/<entity>.inc`,
  services, CSS, JS, fixtures, tests.
- **Accessibilité dès la conception** — semantics, landmarks, heading levels,
  focus order, keyboard handling, ARIA strictly needed.
- **Contenu de démo** — the fixture cases (long, empty optional fields, min
  and max items, special characters, translation).
- **Stratégie de test** — for each acceptance criterion, the level that
  verifies it: PHPUnit unit or kernel, E2E, axe, visual, or manual UAT
  (`testing.md`).

Wait for validation, then record the date in the Plan. **Auto mode**
(`mode: auto` in `state.md`): write the plan, show it, do not wait.

## 5. Branch

```bash
git fetch origin
git switch -c build/<id> origin/develop
```

**No stacking by default.** Only when a dependency is in an unmerged MR:
branch from that MR's branch instead, target it in the MR, and write
« Dépend de !X, à fusionner après » in the description.

## 6. Implementation

Load **`/gm:drupal`** for the backend and follow the starter:

- the `Gm*` entity classes and `entityField()` for field access;
- `gm_router` slugs instead of any hard-coded id or path;
- the `gm_site` services (routes, settings, SEO) rather than new globals;
- theme hooks in `includes/<entity>.inc`, not in the `.theme` file;
- config in `config/sync` through `make cex`, nothing edited by hand there
  except to remove noise the unit did not intend.

Front: Twig and Tailwind with the foundations tokens and components (from
their Contract), vanilla JS only when needed, as a Drupal behavior with
`once()`, declared in the theme's libraries and attached where used. Colours
the editor chooses go through the palette (`--block-*` properties), never a
raw value.

**Porting from the source site**: start from its bundle (fields, template,
behaviour), then rewrite it to the starter — foundations tokens instead of its
CSS, `Gm*` and `entityField()`, `includes/*.inc`, this project's machine
names from the brief. Keep what the CDC asks, drop the rest; the MR says what
was ported and what changed.

Add the unit's fixture `fixtures/<id>.yml` to `gm_demo` (and its assets),
then `make demo unit=<id>`. Add the unit's tests (`tests/e2e/<id>.spec.ts`,
PHPUnit when logic was added) and its screenshot manifest
(`tests/screenshots/units/<id>.ts`).

A bug in a delivered unit found on the way: failing test first, then the fix,
one change at a time, three attempts max before going back to the root cause.

## 7. Self-verification

All of it, before the end validations:

```bash
make phpcs                                  # 0 errors, 0 warnings
make phpstan                                # [OK] No errors
make npm-build                              # no error
make cex && git status --short config/      # nothing left after the unit's commit
make cim                                    # then again: "There are no changes to import."
make cr
make drush c='watchdog:show --count=30'     # no PHP error or warning after rendering the demo pages
make cim && make demo && make test-all      # every delivered unit, not only this one
```

- **Multisite**: built on the driver site; then `make cim-all`,
  `make demo-all` and `make test-all` cover every site (`multisite.md`).
  Never `make cex` on another site than the driver.
- **No baseline, no ignore, no `phpcs:ignore`** added to make a count go down.
- A failing visual reference of another unit is a regression until proven
  otherwise. A reference is updated (`make test-e2e-update c='<spec>'`) only
  for an intended change, with « écart voulu » and the reason in the commit
  body.
- No arbitrary Tailwind value where a token exists (check in
  `design-tokens.md`).
- **Visual comparison with Figma in Chrome** (`screenshots.md`): every
  breakpoint, every state (hover, focus, disabled, error, open), on the demo
  pages. Fix spacing, typography and colour gaps.

## 8. End validations — both, in this order

1. **`drupal-rgaa`** on the real rendering, with the unit id, its demo pages
   and the breakpoints.
2. **`/gm:review`** on the branch diff (`git diff origin/develop...HEAD`, or
   against the parent branch when stacked). Without `gm:review`, review the
   diff yourself for correctness, security (access, XSS in Twig `|raw`,
   untrusted input), cacheability (cache tags and contexts on custom render
   arrays), and the starter's conventions.

Fix every blocking point, re-run Step 7 and the validations it affects. Go
to Step 9 only with a clean verdict from both.

## 9. Delivery

1. **Captures**: `make screenshots unit=<id>`, then upload them
   (`screenshots.md`).
2. **UAT** in French, **local only** — the preprod is filled by the client,
   no content is created there and the UAT never points to it:

   ```markdown
   ## Recette (en local)

   Préalables : `git switch build/<id>`, `make cim`, `make demo`, `make npm-build`.
   Connexion : `make uli` (admin) ou `make drush c='user:login --name=demo-editor'`.

   - [ ] REQ-006 — https://<projet>.dev.localhost/demo/paragraph-faq : cliquer une question → elle s'ouvre, l'autre se ferme.
   - [ ] REQ-006 — au clavier : Tab jusqu'à une question, Entrée → même comportement, focus visible.
   - [ ] Back-office (demo-editor) : /node/add/page → ajouter un bloc FAQ avec 2 questions → enregistré, rendu identique.
   ```

3. **`/gm:merge-request`**: Draft MR to `develop` (or to the parent branch
   when stacked). No ticket and **no chronogram reminder**: it is a build
   project. Description, in French: summary, REQs covered, gaps and
   decisions, UAT, captures, results of phpcs, phpstan, `make test-all`,
   `drupal-rgaa` and the review; for an integration or a config under
   `config_ignore`, a « Prérequis de mise en production » section (accounts,
   keys, env variables, per environment and per site — done by the team,
   never by us). Without `gm:merge-request`: commit (no
   `Co-Authored-By` trailer), push, `glab mr create --draft`.
4. **`.build/`**: the unit row in `state.md` (`review`, branch, MR), the
   brief's Contract completed with what was actually built, new project-wide
   decisions in `decisions.md`. A stable convention discovered here goes to
   the project `CLAUDE.md` (in this MR), never progress.

Then end as the `drupal-build` orchestrator says: one line, `/clear`,
`/drupal-build`.

## Definition of done

- [ ] Every REQ of the unit is covered by an acceptance criterion, each
      criterion by a test level or a UAT line.
- [ ] phpcs, phpstan, build, `make test-all` green; `cex` clean, `cim`
      idempotent; no error in the logs.
- [ ] Compared with Figma at every breakpoint and state.
- [ ] `drupal-rgaa` and the review clean.
- [ ] Draft MR open with captures and UAT; never merged by us.
- [ ] Contract complete; `state.md` updated.
