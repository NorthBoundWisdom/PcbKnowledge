"""HTML rendering for read-only catalog view models."""
from __future__ import annotations

from html import escape
import json
from urllib.parse import quote, urlsplit


def page(title, content):
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + escape(title) + '</title><link rel="stylesheet" href="/static/catalog.css">'
        '<header><a href="/">PcbKnowledge</a><span>Read-only catalog</span></header>'
        '<main>' + content + '</main><script type="module" src="/static/catalog.mjs"></script></html>'
    )


def index(model):
    content = '<h1>Catalog</h1><p>' + escape(model['workspace']) + '</p>'
    for key in ('parts', 'blocks'):
        content += '<h2>' + key.title() + '</h2><ul>'
        for item in model[key]:
            title = item.get('mpn', item['id'])
            url = '/' + key + '/' + quote(item['id'], safe='')
            content += '<li><a href="' + url + '">' + escape(title) + '</a> <small>'
            content += escape(item['verification']) + '</small></li>'
        content += '</ul>'
        if not model[key]:
            content += '<p>No ' + key + ' collected.</p>'
    return page(model['title'], content)


def _external_citation(citation):
    url = citation['url']
    parsed = urlsplit(url)
    safe = parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
    link = 'External source URL unavailable'
    if safe:
        link = '<a href="' + escape(url, quote=True) + '" target="_blank" rel="noopener noreferrer">'
        link += 'Open external HTML source</a>'
    return (
        link + '<br>SHA-256: <code>' + escape(citation['sha256']) + '</code>'
        '<br>Accessed: ' + escape(citation['accessed_on'])
        + '<br>Recorded snapshot identity; the live page may have changed.'
    )


def _citation(citation):
    if not citation:
        return 'No citation (engineering default or unspecified)'
    if citation.get('blocked'):
        return 'Source processing is blocked.'
    if citation['media_type'] != 'application/pdf':
        return _external_citation(citation)
    url = '/sources/' + quote(citation['source'], safe='') + '/content'
    number = escape(str(citation['page']))
    return (
        '<button class="evidence" data-url="' + escape(url) + '" data-page="' + number + '">'
        'PDF p' + number + '</button>'
    )


def record(model):
    content = '<h1>' + escape(model['title']) + '</h1><p>' + escape(model['workspace']) + '</p><p>'
    content += escape(model['record']['verification']) + '</p><div class="review"><section><table>'
    content += '<thead><tr><th>Value</th><th>Content</th><th>Evidence</th></tr></thead><tbody>'
    for row in model['rows']:
        value = row['value']
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        content += '<tr><th>' + escape(row['label']) + '</th><td><code>' + escape(value) + '</code></td><td>'
        content += _citation(row.get('citation')) + '</td></tr>'
    content += '</tbody></table></section><aside>'
    content += '<p id="pdf-status">Select a PDF citation to inspect its page; HTML citations open externally.</p>'
    content += '<canvas id="pdf-page"></canvas></aside></div>'
    return page(model['title'], content)
