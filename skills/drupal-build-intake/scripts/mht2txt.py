#!/usr/bin/env python3
"""Split an MHTML export (Confluence, Word "web page") into markdown text and its images."""

import argparse
import email
import email.policy
import hashlib
import html.parser
import mimetypes
import os
import re
import sys

MAGIC = [
    (b'\x89PNG', '.png'), (b'\xff\xd8', '.jpg'), (b'GIF8', '.gif'),
    (b'RIFF', '.webp'), (b'<svg', '.svg'), (b'<?xml', '.svg'), (b'%PDF', '.pdf'),
]
SKIP = {'script', 'style', 'head', 'title'}


def extension(part, payload):
    for magic, ext in MAGIC:
        if payload[:len(magic)] == magic:
            return ext
    guess = mimetypes.guess_extension(part.get_content_type() or '')
    return guess or '.bin'


class Markdown(html.parser.HTMLParser):
    def __init__(self, images):
        super().__init__(convert_charrefs=True)
        self.images = images
        self.out = []
        self.line = ''
        self.lists = []
        self.row = None
        self.cell = None
        self.skip = 0

    def flush(self):
        text = ' '.join(self.line.split())
        if text:
            self.out.append(text)
        self.line = ''

    def write(self, text):
        if self.cell is not None:
            self.cell += text
        else:
            self.line += text

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in SKIP:
            self.skip += 1
        elif re.fullmatch(r'h[1-6]', tag):
            self.flush()
            self.line = '#' * int(tag[1]) + ' '
        elif tag in ('ul', 'ol'):
            self.flush()
            self.lists.append(tag)
        elif tag == 'li':
            self.flush()
            self.line = '  ' * (len(self.lists) - 1) + '- '
        elif tag == 'tr':
            self.flush()
            self.row = []
        elif tag in ('td', 'th'):
            self.cell = ''
        elif tag in ('p', 'div', 'br', 'blockquote') and self.cell is None:
            self.flush()
        elif tag == 'img':
            src = attrs.get('src', '')
            name = self.images.get(src) or self.images.get(os.path.basename(src)) or src
            self.write(f' [image: {name}] ')

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in ('td', 'th') and self.cell is not None and self.row is not None:
            self.row.append(' '.join(self.cell.split()).replace('|', '/'))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.out.append('| ' + ' | '.join(self.row) + ' |')
            self.row = None
        elif tag in ('ul', 'ol'):
            self.flush()
            if self.lists:
                self.lists.pop()
        elif tag in ('p', 'div', 'li', 'blockquote', 'table') or re.fullmatch(r'h[1-6]', tag):
            if self.cell is None:
                self.flush()

    def handle_data(self, data):
        if not self.skip:
            self.write(data)

    def text(self):
        self.flush()
        return '\n'.join(self.out) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mhtml', help='the exported file (.mht, .mhtml, or a Confluence .doc)')
    parser.add_argument('out', help='output directory: text.md and images/')
    args = parser.parse_args()

    with open(args.mhtml, 'rb') as handle:
        message = email.message_from_binary_file(handle, policy=email.policy.default)
    if not message.is_multipart():
        sys.exit('Not a multipart MHTML file.')

    os.makedirs(os.path.join(args.out, 'images'), exist_ok=True)
    images, pages, seen = {}, [], set()
    for index, part in enumerate(message.walk()):
        if part.is_multipart():
            continue
        payload = part.get_payload(decode=True) or b''
        if part.get_content_type() == 'text/html':
            pages.append(part.get_content())
            continue
        digest = hashlib.md5(payload).hexdigest()
        if not payload or digest in seen:
            continue
        seen.add(digest)
        location = part.get('Content-Location', '') or part.get_filename() or ''
        stem = re.sub(r'[^\w.-]+', '_', os.path.splitext(os.path.basename(location))[0])[:60] or 'part'
        name = f'{index:03d}-{stem}{extension(part, payload)}'
        with open(os.path.join(args.out, 'images', name), 'wb') as handle:
            handle.write(payload)
        for key in (location, os.path.basename(location), part.get('Content-ID', '').strip('<>')):
            if key:
                images[key] = name
                images['cid:' + key] = name

    text = ''
    for page in pages:
        converter = Markdown(images)
        converter.feed(page)
        text += converter.text()
    with open(os.path.join(args.out, 'text.md'), 'w', encoding='utf-8') as handle:
        handle.write(text)
    print(f"{args.out}/text.md: {len(text)} chars, {len(text.splitlines())} lines; "
          f"{len(set(images.values()))} files in {args.out}/images")


if __name__ == '__main__':
    main()
