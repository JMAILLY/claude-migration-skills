# Category — content type

Unit ids `content-<slug>`, branch `build/content-<slug>`. Depends on
`foundations`, on the taxonomies it references, on the recurring components
it displays (card, list), and on the paragraph types its body allows when
they are separate units.

## Deliverables

- **Node type**: machine name from the brief, title label, revisions,
  publishing options, menu settings as the CDC says.
- **Fields**: type, cardinality, required, help text in French; reference
  fields to the taxonomies and media types of the Contracts; the paragraphs
  field with the allowed types.
- **Translation**: per `decisions.md` (asymmetric paragraphs, translatable
  fields listed).
- **Form display**: field groups or tabs if the editor needs them; sidebar
  for meta fields.
- **View modes**: `full`, `teaser`, `card` (and others the mockup uses), each
  with its formatters and template `node--<type>--<mode>.html.twig` built on
  the foundations and recurring components; preprocess in `includes/node.inc`
  through `entityField()`.
- **Listings**: Views for the lists the CDC defines (page size, sort, exposed
  filters, empty state, pager), using the recurring list component; the
  listing page registered as a `gm_router` slug when it is a named target.
- **Pathauto**: pattern using the `gm_router` token
  (`[gm.router:news]/[node:title]`) so the listing and the detail share a
  path prefix the editor controls.
- **SEO**: metatag defaults for the bundle (title, description, image,
  Open Graph, `hreflang` when multilingual) through `GmSiteSEOService` where
  it holds the logic.
- **Permissions**: create / edit own / edit any / delete per editorial role.
- **Breadcrumb**: the listing as parent when the CDC shows it.
- **Page-level options** the CDC gives the editor (show header, show footer,
  indexed or `noindex`, in the site map): fields on the node type, owned by
  this unit, documented in the Contract so `header`, `footer`, the SEO and
  the site map read them. Their default keeps a normal page normal.
- **Generated parts** (table of contents from the `h2` of the body, related
  content excluding the current node, reading time): logic in a service,
  cached with the node's tags, Kernel-tested.

## Control points

- `gm_router` for every link to a named page; no node id in code or config
  beyond `gm_router`.
- Teaser and card render the CDC's fields only (an arbitration in
  `decisions.md` when Figma shows others).
- Views: cache tags (`node_list:<type>`), no `max-age: 0`; exposed filters
  usable by keyboard and labelled; pager announced.
- Dates in the CDC format, in the page's language.
- The editor account can create, edit and translate a node end to end (UAT).
- Pathauto alias generated for the demo nodes that keep pathauto on.

## Contract

Node type and field machine names, cardinalities and targets, view modes and
what each renders, View ids and displays with their paths, the pathauto
pattern, the `gm_router` slug, metatag defaults, the fixture keys.

## Demo

`fixtures/content-<slug>.yml`: enough nodes to fill two pages of the listing
plus one, one complete node (every field, several paragraph types), one
minimal (optional fields empty), one with long title and special characters,
nodes on several terms for the filters, translations when multilingual.
