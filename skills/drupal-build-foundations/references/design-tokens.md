# Design tokens — Figma variables and styles → Tailwind 4 `@theme`

Tailwind 4 is CSS-first: tokens are CSS custom properties declared in
`@theme`, and each namespace generates its utilities. **No
`tailwind.config.js`.** Check the installed version first
(`grep -E '"(tailwindcss|@tailwindcss/[a-z]+)"' package.json`), and read the
theme's entry file to find where `@theme` lives (`src/css/theme.css`, imported
by `src/css/tailwind.css`, in the starter).

## Sources, in order

1. `get_variable_defs` on the style guide nodes **and on one page frame**:
   Figma **variables** (with their modes) and **styles** (text, colour,
   effect). Some scales are only bound in the pages. The fallback values
   inside `get_design_context` output are not values (often stale).
2. `get_design_context` on each style guide component: the values the
   variables do not carry (paddings, border widths, transitions).
3. The documentation frames (grid, breakpoints, colour and spacing tables),
   whose text the intake extracted: values often live there and not in the
   variables. A contradiction between them and the variables was settled in
   the intake (`decisions.md`); apply that decision.
4. Values hard-coded in frames but repeated across the mockup: propose a
   token, list it in the MR as « valeur non tokenisée dans Figma ».

After phase 1, the source of truth is `@theme` and `/styleguide`; the Figma
style guide is not read again.

Tailwind 4 relies on modern CSS (cascade layers, `@property`, `color-mix()`)
and targets Safari 16.4+, Chrome 111+ and Firefox 128+. Older browser targets
in the CDC were settled in the intake (`decisions.md`); apply that decision
here.

## Namespace mapping

| Figma | `@theme` namespace | Utilities | Example |
|---|---|---|---|
| Colour variables / styles | `--color-*` | `bg-*`, `text-*`, `border-*`, `fill-*`, `ring-*` | `--color-primary-700: #0b4f8a;` |
| Font families | `--font-*` | `font-*` | `--font-heading: 'Marianne', system-ui, sans-serif;` |
| Font sizes (text styles) | `--text-*`, plus `--text-*--line-height`, `--text-*--letter-spacing`, `--text-*--font-weight` | `text-*` | `--text-h1: 2.5rem; --text-h1--line-height: 1.2;` |
| Font weights | `--font-weight-*` | `font-*` | `--font-weight-semibold: 600;` |
| Letter spacing | `--tracking-*` | `tracking-*` | `--tracking-caps: 0.08em;` |
| Line heights used alone | `--leading-*` | `leading-*` | `--leading-relaxed: 1.6;` |
| Spacing scale | `--spacing` (base unit) and named `--spacing-*` | `p-*`, `m-*`, `gap-*`, `w-*`… | `--spacing: 0.25rem; --spacing-section: 5rem;` |
| Breakpoints (frame widths) | `--breakpoint-*` | `md:`, `xl:`… | `--breakpoint-md: 48rem;` |
| Container widths | `--container-*` | `max-w-*`, `@container` sizes | `--container-content: 75rem;` |
| Corner radius | `--radius-*` | `rounded-*` | `--radius-card: 0.75rem;` |
| Drop shadows (effects) | `--shadow-*`, `--inset-shadow-*`, `--drop-shadow-*` | `shadow-*`… | `--shadow-card: 0 4px 16px rgb(0 0 0 / 0.08);` |
| Blur | `--blur-*` | `blur-*`, `backdrop-blur-*` | `--blur-overlay: 8px;` |
| Easing | `--ease-*` | `ease-*` (durations: the default `duration-*` scale) | `--ease-out-soft: cubic-bezier(.2,.8,.2,1);` |
| Aspect ratios (image formats from the CDC) | `--aspect-*` | `aspect-*` | `--aspect-card: 4 / 3;` |

**Named spacing tokens shadow the container sizes.** `--spacing-xl` also
generates `w-xl` / `max-w-xl`, which then mean the spacing value, not the
default `--container-xl`. With named spacing tokens (`xs`…`4xl`), write
container widths as `max-w-(--container-content)` and never rely on the
default `max-w-<size>` names.

Reset a namespace before redefining it, so no default token leaks into the
templates (`--color-*: initial;`, `--font-*: initial;`, `--breakpoint-*: initial;`).
Keep the defaults where Figma has nothing to say (the spacing multiplier, the
default durations).

## Naming

- **Two levels for colours**: the palette (`--color-blue-700`) as in Figma,
  then semantic roles that point to it (`--color-primary: var(--color-blue-700);`,
  `--color-text`, `--color-surface`, `--color-border`, `--color-focus`,
  `--color-error`, `--color-success`). Templates use the roles.
- Figma names are slugified: lower case, `/` and spaces → `-`, no
  duplication of the namespace (`Color/Primary/700` → `--color-primary-700`).
- Keep the scale names of the mockup (`h1`…`h6`, `body-lg`, `caption`), not
  Tailwind's (`xl`, `2xl`): the reviewer compares names with Figma.
- Units: `rem` for sizes and spacing (16 px = 1 rem), unitless line heights,
  `em` for letter spacing.

## Responsive values

When a Figma variable has one mode per breakpoint (Mobile / Desktop), declare
the mobile value in `@theme` and redefine the variable at the breakpoint; the
generated utilities follow because they read the variable:

```css
@theme {
  --text-h1: 2rem;
  --text-h1--line-height: 1.2;
}

@layer base {
  :root {
    @variant xl {
      --text-h1: 3rem;
      --text-h1--line-height: 1.1;
    }
  }
}
```

Use `clamp()` only when the mockup shows a continuous scale; otherwise the
steps of the breakpoints are the spec.

## Heading styles decoupled from the tag

The CDC often needs an `h2` that looks like an `h4`. Base styles style the
tags; a utility per level carries the same rules for any element:

```css
@utility heading-1 {
  font-family: var(--font-heading);
  font-size: var(--text-h1);
  line-height: var(--text-h1--line-height);
  font-weight: var(--font-weight-bold);
}

@layer base {
  h1 {
    @apply heading-1;
  }
}
```

Twig components take a `heading_level` and a `heading_style` variable
separately.

## Contrast check (AA)

For every **combination actually used** (text on background, icon on
background, border of a form field, focus ring on its background), compute the
ratio:

- relative luminance `L = 0.2126 R + 0.7152 G + 0.0722 B`, each channel
  `c = s/255`, linearised as `c ≤ 0.04045 ? c/12.92 : ((c+0.055)/1.055)^2.4`;
- ratio `(L1 + 0.05) / (L2 + 0.05)`, lighter over darker.

| Use | Minimum |
|---|---|
| Body text | 4.5:1 |
| Large text (≥ 24 px, or ≥ 18.66 px bold) | 3:1 |
| UI components and graphical objects (field borders, icons that carry meaning, focus indicator) | 3:1 |

**Report, never correct silently.** A failing pair goes into a table in the
MR (pair, ratio, where it is used) and into `decisions.md`, and the human
decides (darker shade, restricted use, accepted with a justification). axe on
`/styleguide` confirms the computed table; it does not replace it.

## Client-customisable colours (palette)

Only when the intake answered yes to « couleurs personnalisables » (site-wide
per site, per block while editing, or both). The colours then live in the
database, not in the CSS: Tailwind cannot compile classes for them, so they
travel as CSS custom properties.

**Model** — unit `recurring-palette`, built right after the foundations:

- Vocabulary `palette`; each term has a label (what the editor sees), a
  machine key (`field_key`, stable, never derived from the editable label)
  and a colour (`color_field` widget, a colour picker). The keys of the
  site-wide roles are fixed (`primary`, `secondary`, `text`, `surface`…).
- Default terms take the Figma colours. In a multisite each site has its own
  terms (separate databases), so each site gets its own colours from the
  same theme. Creating the defaults on the servers follows the intake
  decision: an idempotent deploy hook that runs only when the vocabulary is
  empty, or entry by the client. Locally, the `gm_demo` fixture creates them.
- A `hook_page_attachments` (in `gm_site`, logic in a service) prints one
  inline `<style>` in the head:

  ```css
  :root { --palette-primary: #0b4f8a; --palette-accent: #e8613c; }
  .text-palette-accent { color: var(--palette-accent); }
  ```

  It carries the `taxonomy_term_list:palette` cache tag: a colour change is
  visible at once, nothing else is uncached. The `.text-palette-*` classes
  are what the CKEditor style list offers for « couleur du texte ».

**Tokens** — the semantic roles read the palette, with the Figma value as
fallback, so the site renders even with no term:

```css
@theme {
  --color-primary: var(--palette-primary, #0b4f8a);
  --color-text: var(--palette-text, #1d1d1b);
}

@utility bg-block {
  background-color: var(--block-bg, transparent);
}

@utility text-block {
  color: var(--block-fg, inherit);
}
```

**Per-block choice** — a paragraph's colour fields are entity references to
`palette` terms. The template only sets custom properties that point to the
palette, never a raw colour:

```twig
{% set bg = paragraph.field_background.entity.field_key.value %}
<section class="bg-block text-block"{% if bg %} style="--block-bg: var(--palette-{{ bg|clean_class }})"{% endif %}>
```

**Contrast** — the developer can no longer guarantee the pairs. Record the
intake decision (client responsibility, a list of allowed pairs, or a
warning in the edit form computing the ratio) in `decisions.md`; check the
default pairs as in the section above; `drupal-rgaa` reports content-driven
colours as « dépend de la contribution », blocking only when the default
pairs fail.

## Rules for every template, every unit

- **No arbitrary value when a token exists**: no `p-[18px]`, no
  `text-[#0b4f8a]`, no inline `style=""` for a design value. Check:

  ```bash
  git diff origin/develop -- 'web/themes/custom/**/*.twig' | grep -nE '^\+.*\b[a-z:-]+-\[[^]]+\]'
  ```

  Each hit is either replaced by a token or justified in the MR. The only
  inline `style` allowed sets a `--block-*` property to a `var(--palette-*)`.
- A missing token is added to `@theme` in the unit that needs it and listed
  in the MR, never improvised in a template.
- No comment in CSS.
