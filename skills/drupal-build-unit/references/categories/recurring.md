# Category — recurring elements

Unit ids `recurring-<slug>`, branch `build/recurring-<slug>`. A component or
page used by several other units: cards and teasers, highlights (« mise en
avant »), lists, 403 and 404 pages, cookie banner, forms… as the CDC lists
them. Depends on `foundations`; built before the units that display it.

## Deliverables by kind

**Palette** (`recurring-palette`, when colours are customisable) — the model
in `../drupal-build-foundations/references/design-tokens.md` (« Client-customisable
colours »): vocabulary with key and colour picker, the generated `<style>`,
the roles reading it, default terms per the intake decision, the reference
field every block reuses. In a multisite, one fixture per site with that
site's colours.

**Back to top** — appears after scrolling, a real link or button to the top
with an accessible name, focus moved to the top of the page, respects
`prefers-reduced-motion`.

**Site map** — a page built by hand, or generated from the menus / a View
over the pages flagged « dans le plan du site » (the flag from the content
unit's Contract).

**Card / teaser** — one Twig component with explicit variables (title, url,
image, date, tag, excerpt, `heading_level`), its variants (horizontal,
vertical, with or without image), rendered by a view mode (`card`, `teaser`)
on the entities that use it. The whole card is clickable through **one**
link (the title's, extended with a pseudo-element), not nested links.
Image style and responsive image per breakpoint from the CDC formats.

**Highlight / push** — the component, plus how the editor chooses what is
highlighted (entity reference, view, flag) as the CDC says.

**List** — the listing component (grid or list, empty state, count, pager),
reused by the Views of the content units.

**403 and 404** — real Drupal pages (`system.site` `page.403` / `page.404`
pointing to nodes or routes registered in `gm_router`), with the template and
a way back (search, home, main sections). The HTTP status must stay 403/404.

**Cookie banner** — the module the project uses (or the CDC imposes),
styled with the foundations; refuse as easy as accept, first-layer choice
without scrolling, focus moved to it on first visit, choice persisted,
re-openable from the footer link. No third-party script before consent.

**Forms** (contact, newsletter…) — Webform or a Form API form as the CDC
implies; foundations field components; server-side validation; error summary
at the top linking to the fields; spam protection (the project's captcha);
confirmation message or page; e-mails through the project's mailer (check in
Mailpit; an imposed mailer API is its own `integration` unit). Forms the
editor builds (fields, recipients per subject, success and error messages)
are webforms referenced from a paragraph; the demo creates them as config
entities kept out of `config/sync` (`demo-content.md`).

## Control points

- The component is used by its consumers through its Contract only:
  variables are documented with types and defaults.
- Empty states and long content handled (title on four lines, no image, no
  tag).
- Images: `alt` from the media, decorative when the title says it all; lazy
  loading except above the fold.
- Forms: every field has a label, errors tied by `aria-describedby`,
  `autocomplete` on personal fields, required fields marked and announced.
- 403/404 statuses checked in E2E.

## Contract

Component path and variables; view mode machine names it introduces; image
styles and responsive image ids; for forms, the form/webform id and the route;
for 403/404, the `gm_router` slugs.

## Demo

A fixture per element with every variant and edge case; for forms, the page
that hosts them.
