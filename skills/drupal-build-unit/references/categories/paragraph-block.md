# Category — paragraph block

Unit ids `paragraph-<slug>`, branch `build/paragraph-<slug>`. **One paragraph
type = one unit = one branch = one MR.** A container and its item type
(`faq` + `faq_item`) form one unit. Depends on `foundations`, on the palette
and `media` units it uses, on the taxonomy or recurring component it
references, on the paragraph types it accepts, and on the content type it
lists. A block that carries several independent features (a form builder
with routing rules and a repeatable sub-form) is split into sub-units in the
plan.

## Deliverables

- **Paragraph type(s)**: machine name from the brief, fields with the
  cardinality and requirement the CDC states (min / max items enforced by the
  widget or a constraint), help texts for the editor in French.
- **Translation**: when multilingual, asymmetric — each language owns its
  paragraphs; the host field translatable, the paragraph fields according to
  `decisions.md`.
- **Form display**: widgets the editor can use (media library for images,
  `paragraphs_features` options as the project uses them), collapsed summary
  readable in the host form.
- **Display**: view mode(s), formatters, the template
  `paragraph--<type>.html.twig` built on the foundations components; preprocess
  only when logic is needed, in `includes/paragraph.inc`.
- **Allowed in**: added to the host fields that should offer it (page, news…),
  as the CDC says — and only those. **Containers**: when the block can sit in
  a container (columns, tabs), add it to that container's allowed types in
  this unit; a container that accepts « any block » gets every new type.
- **Colours**: when the palette exists, background and text colour fields are
  references to `palette` terms (shared field storage reused across blocks),
  rendered through `--block-*` properties, never raw values. Full-bleed
  background with the content kept in the container, vertical margins from
  the spacing tokens.
- **Shared fields**: buttons, pictograms, documents and media come from the
  `media` units' Contracts; never a new field type per block.
- Interactive blocks (accordion, tabs, carousel, video): a Drupal behavior,
  vanilla JS, keyboard support, no autoplay without a pause control,
  `prefers-reduced-motion` respected.
- Reuse first: if the starter already ships a paragraph type the plan marked
  « adapt », start from it and remove what the CDC does not need.

## Control points

- Heading level of the block's title fits the page outline (variable
  `heading_level`, usually 2), items one level below.
- Empty optional fields render nothing (no empty wrapper, no stray margin).
- Min and max item counts hold in the editor and render well at max.
- Media: alt text required on informative images; ratio from the CDC formats.
- Rich text uses the editor styles of the foundations.
- Cache metadata of referenced entities bubbles (no `max-age: 0`).

## Contract

Paragraph type and field machine names, cardinalities, target bundles,
translation mode, the hosts it is allowed in, the component and its
variables, the demo page alias.

## Demo

`fixtures/paragraph-<slug>.yml`: one host page `/demo/paragraph-<slug>` with
the block in its common form, plus cases — minimal (optional fields empty),
maximal (max items, long texts), special characters, and the translation when
multilingual.
