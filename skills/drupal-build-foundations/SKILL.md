---
name: drupal-build-foundations
description: >
  Phase 1 of a Drupal site build (drupal-build): translate the whole Figma
  style guide into the design system of a Tailwind 4 Drupal theme — tokens in
  @theme (colours with roles and an AA contrast report, typography and fonts,
  spacing, grid, breakpoints, radii, shadows, transitions), base styles,
  reusable Twig components in every state (buttons, form fields, breadcrumb,
  pager, Drupal messages, tabs, tags, SVG icon sprite), CKEditor content
  styles — plus the local-only gm_demo module (fixtures, Drush generate/purge,
  /styleguide and /styleguide/demo, three locks against deployment) and the
  test tooling (phpunit.xml, Playwright service, axe, visual regression, make
  test targets, PHPUnit in CI). One branch build/foundations, one Draft MR,
  then the unit loop's verification, RGAA, review and delivery steps. Use
  when the drupal-build orchestrator routes here. IMPORTANT: nothing in the
  style guide may be left out; tokens only, no arbitrary values; all
  commands MUST go through Makefile targets.
---

# Build foundations — phase 1

Part of the `drupal-build` campaign. This is the graphic base of the whole
project: **nothing may be missing**. Every later unit builds on these tokens
and components and never reads the Figma style guide again.

Branch `build/foundations`, one Draft MR to `develop`. Shared references, in
`../drupal-build/references/` (relative to this skill's directory):
`build-memory.md`, `demo-content.md`, `testing.md`, `screenshots.md`. This
skill's own: `references/design-tokens.md`.

**No subagents.** Do the work in this conversation; if the context grows,
write the state to `.build/`, commit what is done, and resume after `/clear`.

## Step 0 — Load, branch

```bash
cat .build/state.md
cat .build/units/foundations.md
head -4 .build/requirements.md; grep -E '\| foundations +\|' .build/requirements.md
grep -E '^## D-' .build/decisions.md
git switch develop && git pull --ff-only && git switch -c build/foundations
```

If the branch exists, switch to it and resume from its commits.

## Step 1 — Read the style guide, by node id, one last time

Load **`figma:figma-design-to-code`**. On each style guide node listed in
`units/foundations.md`: `get_variable_defs`, then `get_design_context` and
`get_screenshot` for the components. Never a whole page.

Present the **plan** in French, for validation, before coding: the token
table (Figma name → `@theme` variable → value), the components and their
states, what is missing from Figma and the proposal for it, the contrast
report (`references/design-tokens.md`). Record the validation date in
`units/foundations.md`.

## Step 2 — Tokens, fonts, base styles (commit 1)

Following `references/design-tokens.md`:

- **Colours**: palette and semantic roles. AA contrast of every pair used;
  failing pairs **reported**, not silently corrected.
- **Typography**: families, weights, font files in `src/fonts/` (woff2,
  `font-display: swap`, only the weights used, preload of the body font),
  size scale and line heights, `h1`–`h6` and the decoupled `heading-*`
  utilities, paragraphs, lists, links (default, hover, visited if drawn,
  focus), quotes.
- **Spacing and grid**: spacing scale, containers, columns, gutters and
  margins per breakpoint, breakpoint values (also in the theme's
  `*.breakpoints.yml` when responsive images use them).
- **Radii, shadows, borders, transitions** (and `prefers-reduced-motion`).
- **Palette** (`palette:` in `state.md`): the semantic colour roles already
  read `var(--palette-<key>, <Figma value>)`, and the `bg-block` /
  `text-block` utilities exist, so `recurring-palette` only adds the
  vocabulary and the generated `<style>` (« Client-customisable colours » in
  `references/design-tokens.md`).

```
feat(build): design tokens, fonts and base styles
```

## Step 3 — Base components (commit 2)

Reusable Twig templates, following the theme's existing convention
(`templates/components/*.html.twig` included with `only` in the starter; SDC
if the project already uses them). Each takes documented variables, renders
semantic HTML, and has every state below. Drupal's own templates
(form elements, breadcrumb, pager, status messages, local tasks) are
overridden to call them, so core output and custom output look the same.

| Component | States and variants |
|---|---|
| Button (`<button>` and link-styled-as-button) | every Figma variant; default, hover, active, **focus visible**, disabled; with icon before / after / icon only (accessible name required) |
| Form fields | input (text, email, tel, number, search, password), textarea, select, checkbox, radio, file; label, help text, required marker, error, success, focus, disabled; fieldset/legend; error summary |
| Breadcrumb | current page, truncation on mobile if drawn |
| Pager | full and mini; current page announced |
| Drupal messages | status, warning, error; `role` and live region |
| Tabs | the UI tab component (arrow keys, `aria-selected`) and Drupal's local tasks |
| Tag | link and static variants |
| Icons | SVG sprite through `vite-icon-sprite`; decorative (`aria-hidden`) vs meaningful (`role="img"` + label) |

**Assets.** Export every icon, pictogram, logo and illustration listed by the
intake **as SVG** with the Figma MCP `download_assets`, into the theme sources
so the build compiles them: icons into the sprite source folder
(`src/images/sprites/` in the starter), logos and illustrations into
`src/images/`. Kebab-case file names, `fill="currentColor"` on monochrome
icons so CSS colours them, no fixed `width`/`height` left inside the sprite
symbols. Never a PNG for a vector.

**CKEditor content styles** (`src/css/ckeditor.css`): headings, paragraphs,
lists, links, quotes, tables, images and captions, aligned on the same tokens,
so the editor shows what the front renders.

```
feat(build): base components and editor styles
```

## Step 4 — `gm_demo` and the style guide (commit 3)

Create the module exactly as `../drupal-build/references/demo-content.md`
describes it, **with its locks**: dev split (`module` + partial
`user.role.anonymous`), `deploy.php` exclusions, Make targets that refuse
outside `APP_ENV=local`, Drush commands that refuse too.

- `/styleguide`: every token and every component in every state, one `id`
  per section.
- `/styleguide/demo`: the demo index.
- `fixtures/foundations.yml`: one account per editorial role of the CDC, and
  a basic page whose WYSIWYG text uses every editor style.
- Run the lock proofs listed in the reference and keep their output for the MR.

Backend PHP follows Step 6 of `drupal-build-unit` (`/gm:drupal`, `Gm*`
classes, services, `make cex`).

```
feat(build): local-only demo module and style guide
```

## Step 5 — Test tooling (commit 4)

Exactly as `../drupal-build/references/testing.md` describes it:
`phpunit.xml`, the `playwright` Compose service (profile `e2e`, pinned
version, host resolver rule), `playwright.config.ts` with one project per
breakpoint, `tests/e2e/helpers.ts`, the Make targets (`test`, `test-e2e`,
`test-e2e-update`, `test-all`, `screenshots`), the PHPUnit CI job. First
tests:

- Kernel: `DemoGeneratorTest` (idempotent generation, exact purge).
- E2E: `tests/e2e/foundations.spec.ts` — `/styleguide` and `/styleguide/demo`
  return 200 without console error, axe clean, one reference capture per
  style guide section and breakpoint, keyboard focus visible on every
  interactive component.

Record « E2E et captures locales » in `decisions.md`.

```
build(test): phpunit, playwright, axe and visual regression tooling
```

## Step 5b — Multisite (only with `sites:` in `state.md`)

Following `../drupal-build/references/multisite.md`: the Makefile gets
`SITE` / `SITES`, `--uri` on Drush and the `-all` targets; `sites.php` and one
settings directory per site; `config_ignore` with the per-site config decided
in the intake; `gm_demo` and the tests run on every site. Its own commit:

```
build(multisite): per-site targets, settings and config_ignore
```

## Step 6 — Repository hygiene (amended into commit 4 or its own commit)

- `.gitignore`: `/.build/`.
- `CLAUDE.md` of the project: one line pointing to `.build/state.md` (text in
  `build-memory.md`), plus the stable conventions this phase settled (token
  roles, component include syntax, demo and test targets). No progress.

## Step 7 — The Contract

Fill the **Contract** of `units/foundations.md`; it is what every unit reads
instead of the theme's code: token roles to use (colours, headings,
containers, spacing names), each component's path and variables, the demo
commands and fixture conventions, the test helpers.

## Step 8 — Verification, validations, delivery

Run **Steps 7, 8 and 9 of `drupal-build-unit`** on this branch, with
`/styleguide` and `/styleguide/demo` as the demo pages. In the MR description,
add:

- the token table and the contrast report (failing pairs and the human's
  decision);
- the lock proofs (`grep gm_demo config/sync` empty, module enabled locally
  only);
- the test tooling summary and the first `make test-all` output.

Then update `state.md` (`foundations` → `review`, MR number) and end as the
`drupal-build` orchestrator says. The `/gm:archi-c4` milestone comes after
the merge, in its own conversation.

## Definition of done

- [ ] Every style guide node of `units/foundations.md` is covered by a token or
      a component, or listed as a gap with a decision.
- [ ] `@theme` holds every token; no `tailwind.config.js`; no CSS comment.
- [ ] Every component shows every state on `/styleguide`; focus visible
      everywhere.
- [ ] Contrast report in the MR; no silent colour change.
- [ ] `gm_demo` absent from `config/sync`, excluded from the deploy upload,
      refused by Make and Drush outside `local`.
- [ ] `make test-all` green; references generated in the container.
- [ ] Contract of `units/foundations.md` complete.
