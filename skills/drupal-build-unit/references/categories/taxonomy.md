# Category — taxonomy

Unit ids `taxonomy-<slug>`, branch `build/taxonomy-<slug>`. Depends on
`foundations`; built before the blocks and content types that reference it.

## Deliverables

- **Vocabulary**: machine name from the brief, hierarchy or flat as the CDC
  says, description for editors.
- **Fields** on the term (colour, icon, image, description) only if the CDC
  or the mockup uses them.
- **Translation**: terms translatable when multilingual (label and fields),
  per `decisions.md`.
- **Pathauto** pattern for the terms, only when term pages exist.
- **Term page** if the CDC has one: the listing of the content tagged with it
  (a View with a contextual filter, reusing the recurring list and card
  components), title, description, pager, metatags.
- Without term pages: deny anonymous access to the term route or redirect it
  (the project's module for that, if any), so no empty page is indexed.
- **Permissions**: which editorial role creates, edits and deletes terms.
- Theme hooks in `includes/taxonomy.inc`.

## Control points

- Reference fields that will use it are created by the consuming units, not
  here; this unit documents the target in its Contract.
- Term labels long and with special characters render in tags and filters.
- Term page: 200 for a term with content, empty state for one without.
- Cache tags `taxonomy_term_list` / term tags on listings.

## Contract

Vocabulary machine name, hierarchy depth, term fields, translation mode,
pathauto pattern, term page view id and display, the fixture keys of the demo
terms (`@term:<vocabulary>.<slug>`).

## Demo

`fixtures/taxonomy-<slug>.yml`: every term the CDC names (or a realistic
set), one with a long label, children when hierarchical, translations when
multilingual.
