---
name: drupal-build
description: >
  Orchestrate the build of a complete Drupal 11 site from a specification
  document (cahier des charges, CDC — PDF, docx, MHTML export or link) and a
  Figma mockup read through the Figma MCP, on a Dockerized, Makefile-driven
  starter (PHP 8.4, Vite, Tailwind 4, Paragraphs); multisite and
  client-customisable colours supported. Delivered in small units — design
  foundations, header, footer, recurring elements, media types, one
  paragraph type, one taxonomy, one content type, one integration — each with
  its own branch and Draft MR to develop. Stateless and re-entrant: reads .build/state.md and recomputes
  every status from git and glab, shows progress, offers the units whose
  dependencies are met, and routes to drupal-build-intake (phase 0: CDC and
  Figma analysis, questions, build plan), drupal-build-foundations (phase 1:
  style guide to design system, demo module, test tooling) or
  drupal-build-unit (one unit). One unit per conversation, then /clear and
  /drupal-build. Use when the user wants to build a Drupal site from a CDC
  and a Figma, mentions "drupal-build", "construire le site", "intégrer la
  maquette", or invokes /drupal-build. IMPORTANT: all commands MUST go
  through Makefile targets; the CDC wins over Figma; never merge a MR and
  never write content on preprod or prod.
---

# Drupal build from a CDC and a Figma — orchestrator

The build is a sequence of **units**. Each unit is one branch, one Draft MR to
`develop`, one conversation. This skill owns no code: it reads the state,
shows where the build stands, and routes.

| Phase | Owner | Output |
|---|---|---|
| 0 — Intake | **`drupal-build-intake`** | `.build/` (requirements, decisions, one brief per unit), the validated build plan. No code. |
| 1 — Foundations | **`drupal-build-foundations`** | `build/foundations`: Tailwind tokens, base Twig components, `/styleguide`, `gm_demo`, test tooling. |
| 2 — Units | **`drupal-build-unit`** | `build/<category>-<slug>`: header, footer, recurring element (palette included), media type or shared editing feature, paragraph block, taxonomy, content type, third-party integration. |
| Every unit | **`drupal-rgaa`** | Accessibility verdict on the real rendering, before the review. |

## Source hierarchy

**CDC > Figma > a reasoned proposal.** The CDC wins every conflict with the
mockup; Figma fills what the CDC leaves open; a proposal fills what both
leave open, and is validated by the human when it is not obvious. Every
deviation is recorded in `.build/decisions.md` or in the unit brief. A
blocking ambiguity is a question, never a silent assumption.

## One unit per conversation

Every tool call re-reads the whole conversation; a Figma node or a CDC page
read early is paid for on every later turn. So:

- **Each conversation handles exactly one unit**, then stops and proposes
  `/clear` then `/drupal-build`. A skill cannot clear the conversation itself.
- **Everything that must outlive the session is written to `.build/` before
  proposing `/clear`**: status, branch, MR, decisions, the unit's Contract.
- If the current conversation already carries other work, tell the user to
  `/clear` and re-invoke before routing.
- **No subagents during a unit.** The only exception is the heavy extraction
  of phase 0 (full CDC reading, Figma inventory), and only after the human
  explicitly agrees. When the context grows, the answer is `/clear` + resume.

## Golden rule: everything goes through the Makefile

Never run `php`, `composer`, `drush`, `npm`, `npx` or `phpunit` on the host:
`make drush c='…'`, `make composer c='…'`, `make npm c='…'`, `make test`,
`make test-e2e`, `make demo`. A missing target is **added to the Makefile**,
in the unit's branch, with a `## ` help line in the Makefile's language.
Pass arguments through the variable (`c='…'`, `unit=…`, `SITE=…` in a
multisite): a catch-all rule swallows positional ones.

## Starter assumptions

A build **always starts from the starter**, the up-to-date base. An existing
site may serve as a **source** of blocks to port (recorded by the intake as
`source:` in `state.md`): its code is read only for the bundles a unit brief
names, then adapted to the starter's conventions, never copied as is.

Checked once in Step 0; when one is missing, say so and use the plain Drupal
equivalent instead of inventing the starter's API.

| Expected | Check | Without it |
|---|---|---|
| `gm_utils` (`Gm*` entity classes, `entityField()`) | `ls web/modules/custom/gm_utils` | core entity API |
| `gm_router` (slug → entity) | `ls web/modules/custom/gm_router` | a config-stored mapping, never a hard-coded id |
| `gm_site` services (routes, settings, SEO) | `ls web/modules/custom/gm_site/src` | a site module of the project |
| Theme hooks split in `includes/<entity>.inc` | `ls web/themes/custom/*/includes` | the `.theme` file |
| Tailwind 4, CSS-first `@theme` | `grep tailwindcss package.json` | stop: the foundations reference assumes v4 |
| Config split `dev` enabled when `APP_ENV=local` | `grep -n -B2 -A2 'config_split' web/sites/default/settings*.php` (print the condition, not just the match) | stop and ask: the demo module's first lock depends on it |
| `gm:drupal`, `gm:review`, `gm:merge-request` skills | the skill list | built-in review checklist; plain `git` + `glab` for the MR |

## Step 0 — Where are we?

```bash
git fetch origin --prune
cat .build/state.md 2>/dev/null
git status --short | head
git branch --list 'build/*'
glab mr list --all --source-branch build/<unit> 2>/dev/null   # per unit not yet merged
```

**Recompute every status from git and GitLab; never trust the file alone.**

| Evidence | Status |
|---|---|
| No branch, a `Pending` item of `state.md` blocks it | `blocked` |
| No branch | `planned` (or `ready` when every dependency is `merged`, `review` or `pushed`) |
| Branch pushed and up to date, no MR, `state.md` says « MR on request » | `pushed` (the human chose to wait; counts as `review` for dependants) |
| Branch exists, no MR | `in-progress` |
| Draft or open MR | `review` |
| MR merged | `merged` |
| MR closed without merge | ask the human: abandoned or to redo |

When `glab` cannot run on the host, say so, keep the MR statuses of
`state.md` as they are and mark them « non revérifié » in the progress view.

Before routing, look at the working tree:

- **Current branch is not the integration branch** and no unit is
  interrupted on it: harmless for the intake, but say that any new unit
  branches from an up-to-date `develop` (or its parent's branch when stacked).
- **Uncommitted changes that belong to no unit** (on `develop` or elsewhere):
  never stash or fold them silently. Show `git status --short` and ask: commit
  them apart, fold them into the next unit's opening commit, or leave them.

Write the recomputed statuses and MR numbers back to `state.md`, then route:

| State | Next |
|---|---|
| No `.build/` | invoke **`drupal-build-intake`** |
| `plan:` is `draft` in `state.md` | invoke **`drupal-build-intake`** (resumes at the plan) |
| A unit is `in-progress` with uncommitted changes or unpushed commits | that unit was interrupted: resume it with its sub-skill |
| `foundations` is not `review` or `merged` | invoke **`drupal-build-foundations`** |
| A stacked unit whose parent MR was merged | rebase it on `develop` (`git rebase --onto origin/develop <parent-branch>`), retarget its MR unless GitLab already did it (it does when the parent's source branch is deleted on merge: check the target first), drop the « Dépend de » line, re-run `make test-all` |
| A milestone just closed (foundations merged, or the last unit of a category merged) and its `/gm:archi-c4` line in `state.md` is unchecked | propose `/gm:archi-c4` as this conversation's work (documentation only, never read during a unit) |
| Units are `ready` | show progress, offer the choice (below) |
| Every unit `merged` | the build is done: final `/gm:archi-c4`, summary, delete nothing |

### Progress and choice

Print, in French, a compact view: counts per status, then the `ready` units
grouped by category, each with its dependencies and the open MRs it would
stack on. Example:

```
Avancement : 7/18 fusionnées · 2 en revue · 0 en cours

Disponibles
- Blocs de contenu : paragraph-faq, paragraph-key-figures
- Taxonomies : taxonomy-themes
- Pages de contenu : content-news (empilée sur !14 taxonomy-themes, non fusionnée)
```

Also offer « afficher le plan complet »: the `state.md` table is not readable
as a plan. Render it in French by **dependency waves** (wave 1 = no
dependency, wave n = depends only on earlier waves), one line per unit: id,
one-line scope from its brief, dependencies, status, mode.

Ask which unit to build (`AskUserQuestion` when the list fits). Once chosen,
**print the unit's scope from its brief as a numbered French list** (so the
human can reference items: « retire le 4 »), with its open gaps, before
invoking the sub-skill.

Offer a mode for the chosen unit:

| Mode | When | Effect |
|---|---|---|
| `auto` | simple unit: one paragraph type or taxonomy, no PHP logic, no open gap in its brief, no new dependency | skips the plan validation pause (unit Step 4); everything else still runs |
| `review` | default | pause at the plan validation |
| `step` | large or foundational unit, or on request | pause before **every** step of the sub-skill, showing what the next step will do |

Record the mode in `state.md`, then invoke the sub-skill.

### Pending items

`state.md` has a `Pending` section: open questions that block only some
units (P-1, P-2…). A unit they block is `blocked`, never offered. When the
human gives an interim answer (« garde la police actuelle pour l'instant »),
downgrade it: record a decision in `decisions.md`, rewrite the pending line
as « non bloquant (D-xxx) », update the gap in the affected briefs, recompute.

## Stacking

No stacking by default: a unit branches from an up-to-date `develop`. A unit
may stack only when a dependency is in an **unmerged** MR; it then branches
from that MR's branch, its MR targets that branch, and its description says
« Dépend de !X, à fusionner après ». Step 0 rebases it once the parent lands.

## Context rules (summary — details in `references/build-memory.md`)

- `.build/` is local (`.git/info/exclude` from phase 0, `.gitignore` in the
  foundations MR): no conflict between branches.
- The full CDC and the Figma style guide are read **once**, in phase 0 (the
  style guide once more, by node id, in phase 1). After that: extracts only.
- Figma is queried **by node id** from the unit brief, never by whole page.
- A unit reads its dependencies' **Contract** sections, never their code. The
  one exception is the source site: only the files of the bundle its brief
  names.
- **Multisite** (`sites:` in `state.md`): one codebase and theme, one database
  per site; units are built on the driver site and verified on all of them
  (`references/multisite.md`).
- **Client-customisable colours** (`palette:` in `state.md`): colours travel
  as CSS custom properties from the `palette` terms
  (`../drupal-build-foundations/references/design-tokens.md`).
- The project `CLAUDE.md` gets stable conventions only, plus one line pointing
  to `.build/state.md`. Never progress.
- `/gm:archi-c4` is documentation, regenerated at milestones, never read
  during a unit.

## Cross-cutting rules

- Tailwind 4: tokens in `@theme`, no arbitrary value when a token exists, no
  comment in CSS.
- Code, identifiers, comments and commit messages in English; comments only
  when strictly needed, 3 lines max. Commits without any `Co-Authored-By`
  trailer.
- Human deliverables (questions, plan, UAT, MR description) in French.
- Never merge a MR yourself. Never create content on preprod or prod: the
  client fills them. The UAT runs locally.
- **Push and MR are their own explicit question**, never bundled into
  another choice or mentioned in an option's description: a human who picks
  « continuer » has not agreed to a push. When the human prefers to wait,
  record « MR on request » for the unit in `state.md` (status `pushed`).
- `glab api` cannot send multipart: upload screenshots to a MR with `curl`
  and the token from `glab config get token --host <host>`.
- No chronogram, no tracker ticket: this is a build project.
- Before delivering any unit, `make cim` then `make test-all`: the unit must
  not break the units already merged (visual regression of every demo page
  and of `/styleguide` included), on every site of a multisite.
- Multilingual builds use **asynchronous translation** (each language owns its
  paragraphs) unless `decisions.md` records an exception.

## End of every conversation

Once the routed skill is done and `.build/` is up to date, print:

```
<unit> : <résultat en une ligne> — MR !<iid> (Draft).
Suite : /clear, puis /drupal-build (l'état est dans .build/state.md).
```

## Non-goals

- Do not start a second unit in the same conversation unless the user
  declines the `/clear`.
- Do not re-read the full CDC or browse Figma pages after phase 0.
- Do not use `.build/` or `CLAUDE.md` as a diary.
