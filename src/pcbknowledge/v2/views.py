"""HTML rendering for read-only catalog view models."""
from __future__ import annotations

from html import escape
import json
from urllib.parse import quote


def page(title, content):
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>'+escape(title)+'</title><link rel="stylesheet" href="/static/catalog.css">'
            '<header><a href="/">PcbKnowledge</a><span>Read-only catalog</span></header>'
            '<main>'+content+'</main><script type="module" src="/static/catalog.mjs"></script></html>')


def index(model):
    content='<h1>Catalog</h1><p>'+escape(model['workspace'])+'</p>'
    for key in ('parts','blocks'):
        content+='<h2>'+key.title()+'</h2><ul>'
        for record in model[key]:
            title=record.get('mpn',record['id'])
            content+='<li><a href="/'+key+'/'+quote(record['id'],safe='')+'">'+escape(title)+'</a> <small>'+escape(record['verification'])+'</small></li>'
        content+='</ul>'
        if not model[key]:content+='<p>No '+key+' collected.</p>'
    return page(model['title'],content)


def record(model):
    content='<h1>'+escape(model['title'])+'</h1><p>'+escape(model['workspace'])+'</p><p>'+escape(model['record']['verification'])+'</p><div class="review"><section><table><thead><tr><th>Value</th><th>Content</th><th>Evidence</th></tr></thead><tbody>'
    for row in model['rows']:
        value=row['value'] if isinstance(row['value'],str) else json.dumps(row['value'],ensure_ascii=False,sort_keys=True)
        content+='<tr><th>'+escape(row['label'])+'</th><td><code>'+escape(value)+'</code></td><td>'
        evidence=row['evidence']
        if evidence:
            url='/sources/'+quote(evidence['source'],safe='')+'/content'
            content+='<button class="evidence" data-url="'+escape(url)+'" data-page="'+str(evidence['page'])+'">PDF p'+str(evidence['page'])+'</button>'
        else:content+='No citation'
        content+='</td></tr>'
    content+='</tbody></table></section><aside><p id="pdf-status">Select a citation to inspect its PDF page.</p><canvas id="pdf-page"></canvas></aside></div>'
    return page(model['title'],content)
