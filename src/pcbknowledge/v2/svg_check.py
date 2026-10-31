"""Independent SVG structure and visible-geometry sanity checks, not visual approval."""
import math
import re
from xml.etree import ElementTree

NUMBER = r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'


def _number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Nonfinite SVG coordinate')
    return result


def _geometry(node, tag):
    if tag == 'path':
        path = node.get('d', '')
        numbers = re.findall(NUMBER, path)
        return len(numbers) >= 4 and bool(re.search('[LlHhVvCcSsQqTtAa]', path))
    if tag in ('polygon', 'polyline'):
        numbers = [_number(v) for v in re.findall(NUMBER, node.get('points', ''))]
        return len(numbers) >= 4 and len(set(zip(numbers[::2], numbers[1::2]))) > 1
    if tag == 'rect':
        return _number(node.get('width', '0')) > 0 and _number(node.get('height', '0')) > 0
    if tag == 'circle':
        return _number(node.get('r', '0')) > 0
    if tag == 'ellipse':
        return _number(node.get('rx', '0')) > 0 and _number(node.get('ry', '0')) > 0
    if tag == 'line':
        return (node.get('x1', '0'), node.get('y1', '0')) != (node.get('x2', '0'), node.get('y2', '0'))
    return False


def check_svg(text):
    if '<!ENTITY' in text.upper() or re.search(r'<!DOCTYPE[^>]*\[', text, re.I):
        raise ValueError('SVG entity and internal subset declarations are not supported')
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        raise ValueError('Malformed SVG render') from error
    if root.tag.split('}')[-1] != 'svg':
        raise ValueError('Render is not an SVG document')
    box = [_number(value) for value in root.get('viewBox', '').replace(',', ' ').split()]
    if len(box) != 4 or min(box[2:]) <= 0:
        raise ValueError('SVG requires a finite positive viewBox')
    def visible(node, inherited, hidden=False):
        tag = node.tag.split('}')[-1]
        style = dict(inherited)
        style.update(node.attrib)
        for entry in node.get('style', '').split(';'):
            key, separator, value = entry.partition(':')
            if separator:
                style[key.strip()] = value.strip()
        hidden = hidden or tag in ('defs', 'clipPath', 'mask', 'symbol')
        hidden = hidden or style.get('display') == 'none' or style.get('visibility') in ('hidden', 'collapse')
        hidden = hidden or _number(style.get('opacity', '1')) <= 0
        painted = ((style.get('fill', 'black') != 'none' and _number(style.get('fill-opacity', '1')) > 0)
                   or (style.get('stroke', 'none') != 'none' and _number(style.get('stroke-opacity', '1')) > 0
                       and _number(style.get('stroke-width', '1')) > 0))
        count = int(not hidden and painted and _geometry(node, tag))
        return count + sum(visible(child, style, hidden) for child in node)
    count = visible(root, {})
    if count == 0:
        raise ValueError('SVG render contains no visible geometry')
    return {'status': 'PASS', 'view_box': box, 'visible_geometry_count': count}
