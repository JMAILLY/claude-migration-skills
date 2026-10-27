# paragraph-faq — FAQ block

category: paragraph · depends: foundations · branch: build/paragraph-faq · mode: auto

## Requirements

REQ-006 (text in `requirements.md`)

## Source

- (or) Ported from the source site: paragraph type `faq` — `config/sync/paragraphs.paragraphs_type.faq.yml`, `field.*.paragraph.faq*`, `templates/paragraphs/faq/`.

## Figma nodes

| Breakpoint | State | Node | Frame |
|---|---|---|---|
| desktop | default | 1203:4521 | Bloc FAQ / Desktop |
| desktop | item open | 1203:4610 | Bloc FAQ / Desktop / Open |
| desktop | focus | — | not in Figma: foundations focus ring (D-005) |
| mobile | default | 1203:4702 | Bloc FAQ / Mobile |
| tablet | default | — | simplest functional: mobile layout up to `xl` |

## Gaps and decisions

- G-1 — CDC says one item open at a time; Figma shows two. CDC wins.

## Plan

Validated YYYY-MM-DD (or: auto).

- Objective: …
- Acceptance criteria: AC-1 (REQ-006) …; AC-2 (inferred) …
- Data model: …
- Files: …
- Accessibility by design: …
- Demo content: …
- Test strategy: AC-1 → E2E; AC-2 → UAT; axe + visual on `/demo/paragraph-faq` at every breakpoint.

## Contract

### Data model
- `faq` (paragraph): `field_title` string (1, optional), `field_faq_items` entity_reference_revisions → `faq_item` (1–30).
- `faq_item` (paragraph): `field_question` string (1, required), `field_answer` text_long (1, required).
- Translation: asymmetric, each language owns its items.

### Display
- `faq` default: `h2` title then the accordion; `faq_item` default: disclosure, `button[aria-expanded]` controlling a region.

### Twig components
- `@frontend/components/accordion.html.twig` — `items` (array of `{id, title, body}`), `heading_level` (int, default 3), `single` (bool, default true).

### Routes
- none

### Demo
- `fixtures/paragraph-faq.yml` — keys `node.faq-demo` (all cases), `paragraph.faq.long` (30 items).
- Demo page: `/demo/paragraph-faq`.
