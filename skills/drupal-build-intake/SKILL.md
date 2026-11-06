---
name: drupal-build-intake
description: >
  Phase 0 of a Drupal site build (drupal-build): read the specification
  document (cahier des charges, CDC — PDF, docx, Confluence/Word MHTML export
  or link) in full, with its embedded images, and browse the Figma mockup
  through the Figma MCP; extract every requirement into a REQ-xxx matrix,
  inventory the style guide, page templates, components and breakpoint
  variants; analyse the gaps (CDC vs Figma, inconsistencies inside the CDC,
  pending dated changes, missing breakpoints, browser targets vs Tailwind 4);
  ask every blocking question in one message (multisite, client-customisable
  colours, multilingual, source site to reuse blocks from, breakpoints,
  arbitrations); then produce the build plan — units per category, dependency
  graph, order, branch names, oversized units split — for human validation,
  and create the local .build/ memory. Writes no code. Use when the
  drupal-build orchestrator routes here, or the user asks to analyse a CDC and
  a Figma before building a Drupal site. IMPORTANT: the CDC wins over Figma;
  this is the only phase that reads the full CDC; no subagent without the
  human's explicit agreement.
---

# Build intake — phase 0

Part of the `drupal-build` campaign. This phase reads the inputs in full,
**once**, and turns them into the small files every later session loads
instead. It writes **no code** and creates no branch.

Inputs, asked if missing: the CDC and the Figma file URL; the brand guidelines
(charte) when the CDC points to them outside Figma. The deliverables shown to
the human (questions, gaps, plan) are in French; the `.build/` files are in
English.

Formats: `../drupal-build/references/build-memory.md` and the templates in
`../drupal-build/templates/` (paths relative to this skill's directory).

## Resuming

```bash
ls .build 2>/dev/null && grep -E '^plan:' .build/state.md
```

- `.build/` exists with `plan: draft`: the reading is done. Load `state.md`
  (its `Open questions` section holds the questions asked and not yet
  answered), the decisions titles and the requirements header, then resume
  at Step 4 or 5 with the human's latest answers. Do not re-read the CDC.
- `plan: validated`: nothing to do here; go back to `drupal-build`.

## Context budget and subagents

The CDC and the Figma inventory are the two heaviest reads of the build.
Measure the CDC after extraction (`wc -c`): past roughly 150,000 characters,
or when the Figma file has many pages, **propose** to delegate the extraction
to one subagent per input, and say what it returns (the matrix rows, the node
inventory). Launch nothing without an explicit yes; without it, do the
reading here, section by section, writing rows to `.build/requirements.md` as
you go so nothing depends on the conversation.

## Step 1 — Read the CDC in full

Create the memory first: rows are written as you read, not at the end.

```bash
mkdir -p .build/units .build/figma/raw .build/screenshots
grep -qxF '/.build/' .git/info/exclude || echo '/.build/' >> .git/info/exclude
```

Several candidate files (`cdc.doc`, `cdc(1).doc`, two exports): compare
them with `md5` before asking which one is current.

**Get text out of the file first**, into the scratchpad, never into the
project:

| Input | How |
|---|---|
| PDF | `Read` with `pages`, 20 at a time (the `pdf` skill for tables) |
| docx | the `docx` skill |
| **MHTML export** (Confluence, Word "web page"), whatever its extension: `file` says « news or mail text » or « MIME », or a `MIME-Version` header is in the first lines (a Confluence export starts with `Date:`) | `python3 -I <skill-dir>/scripts/mht2txt.py <file> <scratchpad>/cdc` → `text.md` (headings, nested lists, table rows) and every non-HTML part in `images/`, referenced in the text as `[image: <file>]` |
| Link | the matching connector, or ask for an export |

Confluence sends its images as `application/octet-stream`: never filter the
parts on `image/*` (the script sniffs the bytes). Its captures are
**250 px-high thumbnails**: unreadable as mockups, only useful to locate the
matching Figma nodes. A Confluence export has no page numbers: requirement
sources are `§` only.

Then:

- Extract **every** functional, editorial, technical, accessibility,
  performance, SEO, legal and **integration** requirement into
  `.build/requirements.md`: one line each, with its figures, and its CDC
  location (section number when there are no pages). Leave `Unit` empty.
- Note the imposed display formats (image ratios, file formats, date formats,
  items per list, truncation), the editorial roles, the languages, the
  **browser targets**, the hosting, the **third-party services** (analytics,
  consent tool, mailer API, external scripts, video hosts) and the **external
  references** (sites cited for an animation or a behaviour).
- **Embedded images** are usually mockup captures: list them per section
  (`§4.7: 2 captures`), and use them in Step 2 to find the matching Figma
  nodes. They are not a substitute for Figma.
- **Dated or pending changes** (« modification du JJ/MM, à valider »,
  comments, struck text) are not firm requirements: each becomes a question.
- What is implied but not written becomes a requirement marked « (inféré) »
  only if a unit depends on it; otherwise it is a question.

## Step 2 — Browse Figma through the MCP

Load **`figma:figma-design-to-code`** before any `get_design_context` call;
call `create_session` with the file key first. **Read only**: never call a
tool that writes to the file.

**Never read raw Figma metadata in the conversation.** A real page dump runs
past 100,000 characters (the tool result is then saved to a file) and is
noise anyway. Every dump goes through `scripts/figma-inventory.py` (this
skill's directory), and only its short markdown output is read.

1. **Pages.** `get_metadata` without `nodeId` lists the pages. Show the list
   to the human and ask which ones are archives, separators or drafts,
   rather than dumping everything: a small page's metadata comes back
   **inline** (there is no way to force it to disk), so every dump costs
   context. **Never drop a page on its name alone**: an « OLD » page may hold
   the only frames of a breakpoint. Before dropping one, run the inventory
   on it and read « Screens by width »; ask when it carries widths no
   in-scope page has.
2. **One dump per page, on disk.** `get_metadata` on the page. **Right after
   each call**, copy the result to `.build/figma/raw/<page>.txt`: the file
   name the MCP picks is opaque, and mapping dumps to pages later by call
   order is error-prone. When it came back inline, write it there without
   reading it again.
3. **Inventory.** Run the script, write its output to `.build/figma/`:

   ```bash
   python3 -I <skill-dir>/scripts/figma-inventory.py <dump> --depth 3 --out .build/figma/<page>.md
   python3 -I <skill-dir>/scripts/figma-inventory.py <dump> --node <id> --blocks
   python3 -I <skill-dir>/scripts/figma-inventory.py <dump> --node <id> --texts
   ```

   The inventory gives the tree (section → screen → block) with ids and
   sizes, the screens by width (the breakpoints actually drawn), the
   component instances by name (what is a real component, what is a loose
   frame), and the count of default-named frames. `--blocks` lists the
   direct children of a screen's content frame top to bottom, with their y
   offset, size, component instances and first texts: that is how blocks
   with default names (`Frame 337`) are identified. `--texts` prints the
   text of a documentation frame (grid, colours, spacing, checklists) in
   reading order, one group per direct child (one checklist widget, one
   table); confirm a table with a screenshot, the row grouping is
   positional.
4. **Drill down only where needed**: `get_metadata` on one section or block,
   `get_screenshot` downloaded to the scratchpad at 600–1000 px and viewed
   only to identify an unnamed block, `get_design_context` on **style guide
   components only** in this phase.
5. **Variables.** `get_variable_defs` on the style guide frames **and** on
   one full page frame: the two return different sets (a spacing scale may
   only be bound in the pages, never in the `Espacement` frame). The
   fallback values printed in `get_design_context` (`var(--x, #e94b64)`) are
   often stale: only variables, actual fills and decisions are values.
6. **Unbound values** — a default step, read only: a `use_figma` script
   (load `figma:figma-use` first) that lists the fills and spacings **not
   bound to a variable**, with their counts. A variable may say one colour
   while hundreds of nodes hard-code another (the CDC's): the palette
   defaults and the main colour depend on it. The tool can write, so the
   script only reads and returns data.
7. **Mobile ids.** For every page template, note the node id of each block
   on **every** drawn breakpoint (`--blocks` on each screen), not only the
   desktop: the briefs need them and a unit should not have to drill down.

`.build/figma/raw/` is never read again; the units use the node ids written
in their briefs.

Identify:

- the **style guide** page or frames (colours, typography, spacing, grid,
  buttons, forms, icons, pictograms…), with their node ids;
- the **page templates** per breakpoint (home, listing, detail, form, search,
  403/404…);
- the **components** and their variants and states (hover, focus, open,
  error, empty, long content), and where each appears. **Cross the style
  guide components with the mockup instance counts and the REQ matrix**: a
  component no mockup uses and no REQ asks for (a decorative bar, a
  removable tag, a custom drop-down) is often a leftover of the file it was
  copied from. Flag it « non utilisé, non demandé »: the foundations build
  only what the CDC or a mockup needs;
- the breakpoints actually drawn (frame widths);
- the **documentation frames** (grid, colours, spacing, typography), read with
  `--texts`;
- a **design accessibility page** if there is one (criteria checked, open
  points): its criteria become `a11y` requirements;
- the **assets** to export as SVG: icons, pictograms, logos, illustrations,
  with their node ids (exported in the foundations).

Never call `get_design_context` on a whole page: the output floods the
context and is not needed until the unit that builds it.

## Step 3 — Gaps

Before turning anything into a question, `grep` `.build/requirements.md` for
the component or page: the answer is often already a REQ.

First, a separate list **« Déjà tranché par le CDC »**: the points the CDC
settles itself (« la maquette n'est pas correcte », a section that overrides
a frame). Each one quotes the CDC with its section, and is recorded as
decided. Never restate the CDC's claim about the mockup as a verified fact,
and never mix these items with the ones that need an arbitration.

Then the gaps that need one, in French, seven sections:

1. **Exigence sans maquette** — a REQ with no frame (a listing page, a form,
   an error state).
2. **Maquette sans exigence** — a frame or component no REQ asks for.
3. **Contradictions CDC / Figma** — the CDC wins; each one written as a
   proposed decision, with the CDC quote and the node id.
4. **Incohérences internes au CDC** — a block allowed somewhere but never
   specified, two sections that disagree, a field listed in one table only.
5. **Créa absente** — breakpoints, states or pages not drawn. This is normal,
   not a question: the default is **the simplest functional version** built
   on the foundations (grid, components, tokens). Listed only so the plan
   knows; a question only when the CDC imposes a behaviour the simple version
   would miss.
6. **Composants orphelins** — the style guide components flagged « non
   utilisé, non demandé » in Step 2, proposed for removal.
7. **Navigateurs cibles** — Tailwind 4 targets Safari 16.4+, Chrome 111+ and
   Firefox 128+ (check the installed version's documentation). A CDC that
   requires older browsers is a blocking question: accept the baseline,
   or add fallbacks for the features that break.

## Step 4 — Every blocking question, in one message

Ask once, numbered, each with the default you would apply. Skip what the CDC
settles, stating the answer and its source. Write the questions to the
`Open questions` section of `.build/state.md` as soon as they are asked.

1. **Multisite?** One codebase and one theme for several sites, each with its
   own database? Ask the follow-ups **in the same question** to avoid a
   second round: the sites (directory, local domain), which ones are real
   and which are **test sites** (verified by every unit, no real content),
   the site the build is driven on, what differs per site (config kept per
   site through `config_ignore`, content), and whether the palette is per
   site. When the starter is not ready for it yet (« le multisite arrive sur
   develop bientôt »), record it as a `Pending` item that blocks the
   foundations. See `../drupal-build/references/multisite.md`.
2. **Client-customisable colours?** Can the client change the site's colours
   (per site in a multisite, or globally) and/or pick colours per block while
   editing? If yes: the palette model of `design-tokens.md` (taxonomy terms
   with a colour picker, defaults taken from Figma), who owns contrast, and
   whether the default terms are created by an idempotent deploy hook (only
   when the vocabulary is empty) or entered by the client.
3. **Multilingual?** Languages and default language. The mode is
   **asynchronous translation** — each language owns its paragraphs
   (Paragraphs asymmetric translation) — whatever the CDC's wording: it can
   be loosened later, never tightened. Ask only whether this project is an
   exception.
4. **Source site?** The build starts from the starter, always. Is there an
   existing site whose blocks can be reused to save time? When the CDC names
   it (« créé à partir du site X »), do not ask whether: ask only its local
   path. Which units reuse which of its bundles is settled in Step 5.
5. **Breakpoints.** Those of the CDC; otherwise mobile, tablet and desktop,
   with widths taken from the Figma frames (and the Tailwind breakpoint each
   one maps to).
6. **Arbitration of each gap** from Step 3 that is not a plain « le CDC
   l'emporte », and of each pending dated change.
7. **Starter bundles** to remove (from the Step 5 inventory).
8. **Créa incomplète ou incohérente**, case by case, so `.build/` starts on
   settled ground — for example: a font with no web files or licence; a
   component the CDC needs that Figma lacks (a field type, a state); a
   documentation frame that contradicts the variables (a swatch, a spacing
   value); frames whose validation status is unknown; the open points of a
   design accessibility checklist. Each item gets a proposed default.
9. **Third-party services**: accounts, keys and environments for each
   (analytics, mailer API, consent tool, verification tags); what can be
   tested locally.
10. Editorial roles and their rights, if the CDC is vague.

Record every answer as an entry in `.build/decisions.md` (D-001 onwards) and
empty `Open questions`. A question left unanswered becomes a `Pending` item
(`P-1 … → blocks <units>`) in `state.md`: it blocks only those units.

## Step 5 — The build plan

Inventory the **starter's existing bundles** first (`ls config/sync | grep -E '^(node.type|paragraphs.paragraphs_type|taxonomy.vocabulary|media.type|user.role)'`)
and, when there is a source site, its matching bundles, **side by side** —
the starter often already holds bundles close to the source site's:

| CDC block | Starter bundle | Source site bundle | Verdict | Unit |
|---|---|---|---|---|
| Chiffres clés | `key_figures` | `key_numbers` | adapt the starter's | paragraph-key-figures |

Verdicts: *reuse as is*, *adapt* (starting point of the unit), *port from the
source site*, *remove*.

Present the plan in French, for validation:

- **Units per category**, each with its id, its REQs and a one-line scope:
  - `foundations`;
  - `header`, `footer`;
  - `recurring` — cards and teasers, highlights, lists, breadcrumb rules,
    back to top, 403/404, cookie banner, site map, forms, and the
    **palette** (`recurring-palette`) when colours are customisable;
  - `media` — media types and shared editing features: pictogram library,
    image (with SVG), document, audio, remote video, the reusable button
    field, the CKEditor configuration (buttons, heading levels, palette
    colours);
  - `paragraph` — **one paragraph type = one unit**; a container and its
    item type count as one;
  - `taxonomy`;
  - `content` — content types and their listings;
  - `integration` — one third-party service per unit (analytics, mailer API,
    consent tool, external script, verification tags).
- **Dependency graph**, drawn as an indented list or a Mermaid graph:
  - `foundations` before everything; `recurring-palette` right after it when
    it exists (every block uses it);
  - `media` units before the paragraphs and content types that use them;
  - a taxonomy before what references it; a recurring component (card)
    before what displays it;
  - **paragraph → paragraph**: a container depends on the types it accepts
    (columns → text, image, video). A container that accepts « any block »
    is built early with the types that exist, and **every later paragraph
    unit adds itself** to it;
  - a block that lists content (latest news) depends on that content type;
  - page-level options that drive other units (show header/footer, indexed,
    in the site map) are owned by the content unit and listed in its
    Contract;
  - an integration before the unit that needs it (mailer before the form).
- **Oversized units are split.** A unit that carries several independent
  features (a form builder with routing rules, a repeatable sub-form and a
  mailer API), or whose brief would not fit in one review, becomes ordered
  sub-units `<id>-<part>` (`paragraph-form-builder`, `paragraph-form-routing`),
  each with its branch and MR. The REQs are split between them.
- **Recommended order** — the critical path first, then what unblocks the
  most units.
- **Branch names** — `build/<id>`.
- **Suggested mode** per unit — `auto` for simple units (one paragraph type
  or taxonomy, no PHP logic, no open gap), `step` for the foundations and
  other large units, `review` otherwise.
- **Foundations split** — offer up front to deliver the foundations as
  stacked sub-units, one MR each (`foundations-tokens` → `-components` →
  `-styleguide` → `-tests`): smaller reviews. The delivery steps (test-all,
  RGAA) only fit the last one.
- **Units with no REQ of their own** (a media type, the editor
  configuration, a card shared by listings) are legitimate: their brief
  lists the units and REQs they serve.

Every REQ is assigned to exactly one unit; a REQ left without a unit is a
plan error. Iterate with the human until the plan is validated.

## Step 6 — Complete `.build/`

- `state.md` — the header (CDC, Figma URL and file key, style guide node,
  breakpoints, languages, sites, palette, source site, `gitlab:` from
  `glab repo view`), the milestones, one row per unit,
  `plan: validated YYYY-MM-DD`.
- `requirements.md` — the `Unit` column filled for every row.
- `decisions.md` — the answers of Step 4 and the project-wide arbitrations.
- `units/<id>.md` — one per unit: its REQ ids, its **Figma node ids per
  breakpoint and state** (from the Step 2 inventory and the CDC captures),
  its source bundle when ported from the source site, its gaps, an empty
  Plan, and a Contract with the names already decided (machine names,
  component names). `units/foundations.md` lists every style guide node.

Check: `wc -l .build/state.md` (100 lines max), every REQ has a unit, every
unit file has at least one node row per drawn breakpoint or a gap explaining
why not.

After this step **nobody reads the full CDC again**. A later doubt is settled
by opening the one section cited in `requirements.md`.

## End

```
Phase 0 terminée — <n> exigences, <n> unités, <n> décisions. Plan validé le <date>.
Suite : /clear, puis /drupal-build (démarre les fondations).
```

## Non-goals

- No code, no branch, no config change, no Composer package.
- No `get_design_context` on templates or page frames: units do it, by node id.
- No silent assumption: an ambiguity that blocks a unit is a question.
