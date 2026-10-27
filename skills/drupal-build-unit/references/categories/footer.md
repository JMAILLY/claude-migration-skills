# Category — footer

Unit id `footer`, branch `build/footer`. Depends on `foundations`.

## Deliverables

- **Menus**: footer menus as drawn (one Drupal menu each), legal menu
  (mentions légales, données personnelles / RGPD, cookies, accessibilité —
  the accessibility statement link is mandatory in France, « Accessibilité :
  non/partiellement/totalement conforme »), plan du site if the CDC asks.
- **Contact details**: address, phone (`tel:` link), email — editable in the
  back office (block content or `gm_site` settings), never in the template.
- **Social networks**: links with accessible names (« LinkedIn — nouvelle
  fenêtre » when `target="_blank"`), icons from the sprite.
- **Logos / partners** if drawn, with alt text or hidden when decorative;
  separate desktop and mobile versions through a `<picture>`.
- **Consent link** (« gestion des cookies ») that reopens the consent tool.
- **Third-party footer** (a script the client's group provides): its own
  `integration` unit; the footer only reserves its place.
- **Per-page footer toggle** when the CDC has one: from the content unit's
  Contract.
- **Newsletter or contact form** in the footer only if the CDC asks; then it
  follows `recurring.md` (forms).
- Back-to-top link if drawn.
- Theme hooks in `includes/block.inc` / `navigation.inc`.

## Control points

- One `footer` (`contentinfo`) landmark; each menu a `nav` with a distinct
  `aria-label`.
- Every external link announced as opening a new window when it does.
- Contrast on the footer background (often dark): text and focus ring.
- Contact and social data editable by the editor role (check with the demo
  account).
- Cache tags of the config or block content used.

## Contract

Footer menu machine names, the block or settings holding contact and social
data, the legal pages' `gm_router` slugs (`legal-notice`, `privacy`,
`accessibility`, `cookies`).

## Demo

`fixtures/footer.yml`: footer and legal menus, contact data with long values,
every social network drawn, legal pages as basic pages with `gm_router`
entries.
