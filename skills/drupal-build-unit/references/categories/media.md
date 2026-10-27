# Category — media and shared editing features

Unit ids `media-<slug>`, branch `build/media-<slug>`. The media types and the
editing features every block reuses. Depends on `foundations` (and on
`recurring-palette` when the feature offers colours); built before the
paragraphs and content types that use them.

## Typical units

| Unit | Delivers |
|---|---|
| `media-image` | Image media type, alt text required (or explicitly decorative), allowed formats from the CDC (SVG needs its own handling: no image style, sanitised upload, `width`/`height` set), image styles and responsive images per CDC format |
| `media-pictogram` | Pictogram library the client fills: a media type (SVG) or a taxonomy with an SVG field, picker in the edit form, rendering inline at the size the CDC sets (« même hauteur que les majuscules » → `1cap`/`1em`), decorative by default |
| `media-document` | Document media type, allowed extensions, rendering with the download label, the format and the size computed from the file (never typed), icon from the sprite |
| `media-audio` | Audio media type (mp3), player built on the foundations (play/pause button with a name, elapsed and total time, progress or waveform if drawn), keyboard operable, no autoplay |
| `media-video` | Remote video (oEmbed: Vimeo, YouTube) behind the consent tool, play button from the sprite, title for the iframe, a placeholder until consent |
| `media-button` | The reusable button/link field: label, target (internal page or URL), style (default or custom with palette colours), the chevron rule (shown when the target is another page), the same rendering as the foundations button |
| `media-editor` | CKEditor 5 configuration: the text formats, heading levels allowed, inline buttons (a style or a plugin producing the button markup), palette text colours (`text-palette-*` styles), links inheriting the text colour, paste cleanup |

Split or merge them as the CDC needs: a CDC with images only needs
`media-image` and `media-editor`.

## Control points

- Every media type: the media library widget works for the editor role; the
  source field's allowed extensions and maximum size match the CDC.
- Alt text: required for informative images, an explicit « décorative »
  choice otherwise; never filled with the file name.
- Remote media: nothing loads from the third party before consent.
- Computed values (file size, format, duration) come from the file, cached
  with the media's tags.
- The editor features render identically in CKEditor (`ckeditor.css`) and on
  the page.

## Contract

Media type and source field machine names, allowed extensions, view modes
and the image styles / responsive images they use, the button field type or
paragraph (and its Twig variables), the text formats and the styles they
offer.

## Demo

One media per type and per edge case (portrait, landscape, square, SVG, long
document name, long audio, video without consent), plus a page whose WYSIWYG
uses every editor feature. Remote video needs the network when the fixture is
generated (oEmbed fetch); keep one, with a stable public URL.
