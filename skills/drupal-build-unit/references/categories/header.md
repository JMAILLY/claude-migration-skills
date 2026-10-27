# Category — header

Unit id `header`, branch `build/header`. Depends on `foundations`; on the
content units only when a menu entry or the search needs their route.

## Deliverables

- **Region and blocks**: site branding (logo as a link to the home page, SVG
  inline or `<img>` with the site name as accessible name), main menu,
  secondary/utility menu if drawn, search if the CDC asks, language switcher when the site is
  multilingual. Blocks placed through config, not hard-coded in
  `page.html.twig`.
- **Skip links**: first focusable element, at least « Aller au contenu »
  (to `#main-content`), plus « Aller au menu » / « Aller à la recherche » when
  the CDC or RGAA scope asks.
- **Main menu**: the depth the CDC defines; desktop dropdowns or mega menu as
  drawn; active trail styled. Built from pages the editor creates and places
  (position and URL chosen in the back office).
- **Sections without a page** (a heading that only groups pages): a menu link
  to `route:<nolink>` rendered as a `<button>` that opens its submenu; never a
  link to an empty node. The breadcrumb shows it as plain text, not a link.
- **Grouped external links** (a « Connexion » entry listing external
  services): a menu or a link field with an editable section label, each
  entry with label and URL, same dropdown behaviour as the other sections.
- **Per-page header toggle** when the CDC has one: read from the content
  unit's Contract (field and value), applied in `includes/page.inc`.
- **Mobile menu**: a real `<button>` with `aria-expanded` and `aria-controls`,
  `Escape` closes it and returns focus to the button, focus kept inside while
  open (or the rest made `inert`), body scroll locked, closes on resize to
  desktop.
- **Search**, only when the CDC asks for it: the `gm_search` header form
  block, styled with the foundations form components, `role="search"`
  landmark, a visible or visually hidden label. Without it, remove the
  starter's search block from the header.
- **Language switcher** (multilingual): links to the **translation** of the
  current page (not the home), `lang` and `hreflang` on each link, the current
  language marked (`aria-current`), hidden languages without translation per
  the CDC.
- **Sticky / shrinking header** only if drawn; respects
  `prefers-reduced-motion`.
- Theme hooks in `includes/navigation.inc` / `block.inc`; menus as Twig
  components from the foundations where possible.

## Control points

- Landmarks: one `header` (`banner`), one `nav` per menu with a distinct
  `aria-label`.
- Tab order matches the visual order at every breakpoint.
- Dropdowns open on click/Enter (hover alone is not enough), close on `Escape`
  and on focus leaving.
- Logo and icon-only buttons have an accessible name.
- Menu items come from Drupal menus (editable in the back office), never from
  the template.
- Cache: menu blocks keep `route.menu_active_trails` contexts; no
  `max-age: 0`.
- Mobile menu tested at 320 px width and at 200 % zoom.

## Contract

Menu machine names and depth; block ids and regions; the mobile menu's
JS behavior name and the events it reacts to; the skip link targets; the
language switcher block id.

## Demo

`fixtures/header.yml`: main menu with the maximal depth and a long label,
utility menu, enough entries to wrap at the tablet width.
