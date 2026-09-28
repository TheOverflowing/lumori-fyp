"""Disposable frontend performance fixture: synthetic data, no accounts/providers.

Run on localhost with --static-dir to compare a frozen frontend snapshot.
"""
import argparse
import asyncio
import re
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
PROBE = r"""
const panel=document.createElement('aside');panel.id='perf-panel';
panel.style.cssText='position:fixed;right:12px;bottom:12px;z-index:9999;background:#fff;color:#222;padding:10px;border:1px solid #999;max-width:420px;font:12px monospace';
panel.innerHTML='<button id="perf-reset">Start sample</button> <button id="perf-change">Change one source</button> <button id="perf-result">Read sample</button><pre id="perf-output">Ready</pre>';
document.body.append(panel);
let reads=0,added=0,removed=0,addedRows=0,removedRows=0,longTasks=[],frames=[],last=0,active=false,start=0;
const descriptor=Object.getOwnPropertyDescriptor(Element.prototype,'scrollHeight');
Object.defineProperty(Element.prototype,'scrollHeight',{...descriptor,get(){if(active&&this.tagName==='TEXTAREA')reads++;return descriptor.get.call(this);}});
const elementCount=node=>node.nodeType===1?1+node.querySelectorAll('*').length:0;const rowCount=node=>node.nodeType===1?(node.matches('.collection-row')?1:0)+node.querySelectorAll('.collection-row').length:0;
new MutationObserver(records=>{if(active)for(const r of records){for(const n of r.addedNodes){added+=elementCount(n);addedRows+=rowCount(n);}for(const n of r.removedNodes){removed+=elementCount(n);removedRows+=rowCount(n);}}}).observe(document.querySelector('#page')||document.querySelector('#perf-form'),{childList:true,subtree:true});
if(PerformanceObserver.supportedEntryTypes.includes('longtask'))new PerformanceObserver(list=>{if(active)longTasks.push(...list.getEntries().map(e=>e.duration));}).observe({type:'longtask'});
function frame(now){if(active){if(last)frames.push(now-last);last=now;requestAnimationFrame(frame);}}
document.querySelector('#perf-reset').onclick=()=>{reads=added=removed=addedRows=removedRows=0;longTasks=[];frames=[];last=0;start=performance.now();if(!active){active=true;requestAnimationFrame(frame);}document.querySelector('#perf-output').textContent='Recording';};
document.querySelector('#perf-change').onclick=()=>fetch('/__perf/change',{method:'POST'});
document.querySelector('#perf-result').onclick=()=>{active=false;const sorted=frames.toSorted((a,b)=>a-b);document.querySelector('#perf-output').textContent=JSON.stringify({duration_ms:Math.round(performance.now()-start),textarea_layout_reads:reads,added_nodes:added,removed_nodes:removed,added_rows:addedRows,removed_rows:removedRows,long_tasks:longTasks.length,long_task_ms:Math.round(longTasks.reduce((a,b)=>a+b,0)),frame_gap_p95_ms:Math.round(sorted[Math.floor(sorted.length*.95)]||0),gaps_over_50ms:frames.filter(x=>x>50).length},null,2);};
"""


def create_fixture(static_dir):
    app = FastAPI()
    static_dir = Path(static_dir)
    app.mount('/static', StaticFiles(directory=static_dir))
    @app.middleware('http')
    async def uncached_fixture(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response
    changed = {'revision': 0}
    course = {'id': 'perf-course', 'name': 'Frontend performance fixture'}
    documents = [{'id': f'doc-{n}', 'course_id': course['id'], 'name': f'Course source {n:03d}.md',
        'pages': 10, 'chunks': 24, 'status': 'ready', 'index_current': True, 'enabled': True,
        'deleted_at': None, 'active_jobs': [], 'figures': []} for n in range(80)]
    contents = [{'id': f'content-{n}', 'course_id': course['id'], 'course_name': course['name'],
        'title': f'Machine learning practice {n:03d}', 'version': 1, 'status': 'draft',
        'material': 'quiz', 'created_at': '2026-09-23T06:00:00Z'} for n in range(80)]

    @app.get('/')
    async def index():
        html = (static_dir / 'index.html').read_text()
        html = re.sub(r'(/static/[^"?]+\.css)', lambda match: match[1] + '?fixture=' + str(
            (static_dir / match[1].split('/static/')[1]).stat().st_mtime_ns), html)
        return HTMLResponse(html.replace('</body>', '<script type="module" src="/__perf/probe.js"></script></body>'))

    @app.get('/__perf/probe.js')
    async def probe():
        return Response(PROBE, media_type='text/javascript')

    @app.get('/__perf/form')
    async def form():
        fields = ''.join(f'<label>Field {n}<textarea aria-label="Field {n}">A course note for question {n}.</textarea></label>' for n in range(80))
        return HTMLResponse(f'''<!doctype html><html lang="en"><head><link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/inputs.css"></head><body><main><h1>Autosize benchmark</h1><form id="perf-form">{fields}</form></main><script type="module" src="/__perf/probe.js"></script><script type="module">import {{mountInputControls}} from '/static/input-controls.js';mountInputControls(document.querySelector('#perf-form'));</script></body></html>''')

    @app.post('/__perf/change')
    async def change():
        changed['revision'] += 1
        return changed

    @app.get('/api/auth/session')
    async def session():
        return {'user': {'id': 'performance-fixture', 'display_name': 'Fixture', 'email': 'fixture@example.test'}, 'csrf_token': 'fixture-only'}

    @app.get('/api/courses')
    async def courses():
        return [course]

    @app.get('/api/documents')
    async def docs():
        await asyncio.sleep(.08)
        return [doc | {'chunks': doc['chunks'] + (changed['revision'] if n == 0 else 0)} for n, doc in enumerate(documents)]

    @app.get('/api/contents')
    async def materials():
        await asyncio.sleep(.08)
        return contents

    @app.get('/api/jobs')
    async def jobs():
        return []

    @app.get('/api/status')
    async def status():
        return {'capabilities': {k: {'configured': False} for k in ('text', 'embedding', 'image', 'speech')}, 'auto_exploration': {'available': False}}

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8775)
    parser.add_argument('--static-dir', type=Path, default=ROOT / 'app/static')
    args = parser.parse_args()
    uvicorn.run(create_fixture(args.static_dir), host='127.0.0.1', port=args.port)
