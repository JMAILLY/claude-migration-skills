#!/usr/bin/env python3
"""Turn a Figma MCP get_metadata dump into a short markdown inventory."""

import argparse
import collections
import html
import json
import re
import sys

NODE = re.compile(r'^(\s*)<([\w-]+)\s+(.*?)\s*/?>\s*$')
ATTR = re.compile(r'([\w-]+)="([^"]*)"')
STRUCTURE = {'canvas', 'section', 'frame', 'instance', 'symbol', 'component', 'component-set', 'widget'}


def load(path):
    raw = open(path, encoding='utf-8').read()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return ''.join(part.get('text', '') for part in data if isinstance(part, dict))
    except json.JSONDecodeError:
        pass
    return raw


def number(attrs, key):
    return float(attrs.get(key, 0) or 0)


def parse(text):
    nodes = []
    stack = []
    for line in text.splitlines():
        match = NODE.match(line)
        if not match or match.group(2).startswith('/'):
            continue
        attrs = {key: html.unescape(value) for key, value in ATTR.findall(match.group(3))}
        if 'id' not in attrs:
            continue
        depth = len(match.group(1)) // 2
        while stack and stack[-1]['depth'] >= depth:
            stack.pop()
        parent = stack[-1] if stack else None
        node = {
            'depth': depth,
            'type': match.group(2),
            'id': attrs['id'],
            'name': attrs.get('name', ''),
            'width': round(number(attrs, 'width')),
            'height': round(number(attrs, 'height')),
            'x': number(attrs, 'x') + (parent['x'] if parent else 0),
            'y': number(attrs, 'y') + (parent['y'] if parent else 0),
            'parent': parent['type'] if parent else None,
        }
        nodes.append(node)
        stack.append(node)
    return nodes


def subtree(nodes, node_id):
    for index, node in enumerate(nodes):
        if node['id'] == node_id:
            result = [node]
            for child in nodes[index + 1:]:
                if child['depth'] <= node['depth']:
                    break
                result.append(child)
            return result
    sys.exit(f'Node {node_id} not found.')


def bucket(width):
    if width <= 480:
        return 'mobile'
    if width <= 1100:
        return 'tablet'
    return 'desktop'


def inventory(nodes, depth):
    base = nodes[0]['depth']
    out = [f"# {nodes[0]['name']} ({nodes[0]['id']})", '']

    screens = [n for n in nodes if n['type'] == 'frame' and n['parent'] in ('canvas', 'section')
               and n['width'] >= 320 and n['height'] >= 400]
    widths = collections.Counter(n['width'] for n in screens)
    out.append('## Screens by width')
    out.append('')
    for width, count in sorted(widths.items()):
        out.append(f'- {width}px ({bucket(width)}): {count}')
    out += ['', '## Tree', '']
    for node in nodes:
        level = node['depth'] - base
        if level > depth or node['type'] not in STRUCTURE:
            continue
        out.append(f"{'  ' * level}- {node['type']} `{node['id']}` {node['name']} — {node['width']}x{node['height']}")

    instances = collections.Counter(n['name'] for n in nodes if n['type'] == 'instance')
    out += ['', '## Component instances', '']
    out += [f'- {name}: {count}' for name, count in instances.most_common()]

    unnamed = sum(1 for n in nodes if n['type'] == 'frame' and re.fullmatch(r'(Frame|Group) \d+', n['name']))
    types = collections.Counter(n['type'] for n in nodes)
    out += ['', '## Counts', '', f"- {dict(types)}", f'- frames with a default name: {unnamed}']
    return '\n'.join(out) + '\n'


def middle(node):
    return node['y'] + node['height'] / 2


def texts(nodes, tolerance=12):
    out = [f"# Texts under {nodes[0]['name']} ({nodes[0]['id']}), in reading order", '']
    items = sorted((n for n in nodes if n['type'] == 'text' and n['name'].strip()), key=lambda n: (middle(n), n['x']))
    rows = []
    for item in items:
        if rows and abs(middle(item) - middle(rows[-1][0])) <= tolerance:
            rows[-1].append(item)
        else:
            rows.append([item])
    for row in rows:
        cells = [' '.join(n['name'].split()) for n in sorted(row, key=lambda n: n['x'])]
        out.append('- ' + ' | '.join(cells))
    return '\n'.join(out) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dump', help='get_metadata output saved to a file (JSON array or raw XML)')
    parser.add_argument('--node', help='restrict to the subtree of this node id')
    parser.add_argument('--depth', type=int, default=3, help='tree depth below the root (default 3)')
    parser.add_argument('--texts', action='store_true', help='list the text nodes instead of the tree')
    parser.add_argument('--out', help='write to this file instead of stdout')
    args = parser.parse_args()

    nodes = parse(load(args.dump))
    if not nodes:
        sys.exit('No node found in the dump.')
    if args.node:
        nodes = subtree(nodes, args.node)
    result = texts(nodes) if args.texts else inventory(nodes, args.depth)
    if args.out:
        open(args.out, 'w', encoding='utf-8').write(result)
        print(f'{args.out}: {len(result.splitlines())} lines')
    else:
        sys.stdout.write(result)


if __name__ == '__main__':
    main()
