# Build memory — `.build/`

A session loads only what the current unit needs. The CDC and the Figma style
guide are read in full once (phase 0); every later session works on extracts
written here. The templates are in `../templates/` (relative to this file).

## Location and versioning

- `.build/` sits at the project root and is **never committed**: it would
  conflict on every branch. Phase 0 adds it to `.git/info/exclude`; the
  foundations MR adds `/.build/` to `.gitignore` for the team.
- It is the driving developer's working memory. To hand the build over, copy
  the folder; everything else is recomputed from git and GitLab.
- The project `CLAUDE.md` holds one line pointing here and the stable
  conventions found during the build (rules, not progress):

  ```markdown
  - Site build in progress: plan and state in `.build/state.md` (local, driven by /drupal-build).
  ```

## Files

| File | Content | Loaded |
|---|---|---|
| `state.md` | Compact index, **100 lines max**: inputs (CDC, Figma URL and file key, breakpoints, languages, sites, palette, source site), milestones, one line per unit. | Every session, in full |
| `requirements.md` | `REQ-xxx` matrix: condensed text, CDC location, unit. | Only the current unit's rows |
| `units/<id>.md` | Unit brief: REQs, Figma node ids per breakpoint and state, gaps and decisions, validated plan, **Contract**. | The current unit in full; **only the Contract** of its dependencies |
| `decisions.md` | Project-wide decisions, short ADR (3–5 lines each). | Titles first, then only the relevant entries |
| `figma/<page>.md` | Page inventory from `figma-inventory.py`: tree with node ids, screens by width, component instances. | Phase 0; later only to find a node id missing from a brief |
| `figma/raw/` | Raw `get_metadata` dumps. | Never read by the model, only by the script |
| `screenshots/` | Local captures (`make screenshots`). | Never read by the model |

## Loading commands

```bash
cat .build/state.md
head -4 .build/requirements.md; grep -E '\| <unit-id> +\|' .build/requirements.md
cat .build/units/<unit-id>.md
sed -n '/^## Contract/,$p' .build/units/<dependency-id>.md
grep -E '^## D-' .build/decisions.md
sed -n '/^## D-007/,/^## D-/p' .build/decisions.md
```

Never `cat` the whole `requirements.md` or `decisions.md` during a unit.

## `state.md`

- The header fields are written by phase 0 and change only through a decision.
- `plan:` is `draft` until the human validates the plan, then
  `validated YYYY-MM-DD`.
- One table row per unit. `status` is one of `planned`, `ready`,
  `in-progress`, `review`, `merged`, `blocked`; Step 0 of `drupal-build`
  recomputes it from git and `glab` and rewrites the row.
- `depends` lists unit ids, comma-separated; `-` for none (only `foundations`).
- `mode` is `review` (default: the plan is validated before coding) or `auto`.
- The milestones list carries one checkbox per `/gm:archi-c4` regeneration:
  after foundations, then after each category.
- Over 100 lines means something that belongs elsewhere landed here: move it
  to a unit brief or to `decisions.md`.

## `requirements.md`

- One row per requirement, `REQ-001` onwards, never renumbered. A requirement
  dropped by the client stays, with `dropped (D-xxx)` as unit.
- Text **condensed** to one line: what must be true, with the figures (page
  size, limits, formats). The CDC wording is not copied.
- `Source` points into the CDC (`p. 14 §3.2`) so a doubt is settled by opening
  that page only.
- `Type`: `functional`, `editorial`, `technical`, `a11y`, `performance`,
  `seo`, `legal`.
- `Unit`: exactly one unit id. A requirement shared by several units goes to
  `foundations` or `recurring-*`, and the others reference it.

## `units/<id>.md`

- Ids: `foundations`, `header`, `footer`, then `<category>-<slug>` with
  category `recurring`, `media`, `paragraph`, `taxonomy`, `content`,
  `integration`. Slugs are the future machine names in kebab case. A split
  unit gets ordered sub-units `<id>-<part>`. Branch: `build/<id>`.
- **Source**: when the unit ports a block from the source site, the bundle
  and its files there; the only code outside this project a unit may read.
- **Figma nodes**: one row per breakpoint and state (default, hover, focus,
  open, empty, error, long content). A breakpoint or state not drawn is a row
  with node `—` and « simplest functional ».
- **Gaps and decisions**: unit-scoped arbitrations. Project-wide ones go to
  `decisions.md` and are only referenced here.
- **Plan**: written in unit Step 4, with its validation date (or `auto`).
- **Contract**: what the unit exposes to the others. A dependent unit reads
  only this section; if it is not enough, **complete the Contract**, do not
  read the code. Keep it factual and short:
  - data model: machine names of bundles and fields, cardinality, target
    bundles, translatability;
  - display: view modes and what each renders;
  - Twig components: path and variables, with types and defaults;
  - routes: `gm_router` slugs, Views paths and displays, pathauto patterns;
  - demo: the fixture keys other fixtures may reference (`@term:themes.energy`).

## `decisions.md`

Short ADR, numbered `D-001` onwards, never renumbered; a reversed decision
gets a new entry that supersedes the old one.

```markdown
## D-003 — Breakpoints: mobile 375, tablet 768, desktop 1440
Source: CDC silent; Figma frames 375 / 1440; tablet proposed, validated 2026-11-04.
Decision: three breakpoints, Tailwind `md` = 48rem, `xl` = 90rem; tablet derived from desktop.
Consequence: every unit captures and tests three widths.
```

Typical entries: multilingual mode, breakpoints, CDC/Figma arbitrations that
hold for the whole site, colour pairs that fail contrast, E2E kept local, the
fate of the starter's existing bundles.

## Things that are not build memory

- `/gm:archi-c4` describes the architecture. Regenerate it at milestones,
  never read it during a unit.
- Commit messages and MR descriptions are the delivery record; `state.md`
  only keeps the MR number.
