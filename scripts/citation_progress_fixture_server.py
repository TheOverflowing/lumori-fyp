"""Isolated citation / progress browser QA; no external provider calls.

Run: .venv/bin/python -m uvicorn scripts.citation_progress_fixture_server:create_fixture --factory --host 127.0.0.1 --port 8768
Account: fixture@example.test / Fixture browser password 2026!
Content: /#content/citation-fixture-content
Progress: /__ui/progress (all timings and events are explicitly simulated)

Each start creates a fresh temporary database. The historical EN08 experiment
is read only; its lesson and citation identifiers are preserved verbatim.
"""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import mkdtemp

from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.store import dumps, now


CONTENT_ID = "citation-fixture-content"
EMAIL = "fixture@example.test"
PASSWORD = "Fixture browser password 2026!"
ROOT = Path(__file__).resolve().parents[1]


PROGRESS_HTML = r'''<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lumori · isolated progress fixture</title>
<link rel="stylesheet" href="/static/style.css">
<link rel="stylesheet" href="/static/material.css">
<link rel="stylesheet" href="/static/preferences.css">
<link rel="stylesheet" href="/static/inputs.css">
<link rel="stylesheet" href="/static/generation-progress.css">
<style>
body { padding: 24px; }
.fixture-tools { max-width: 1100px; margin: 0 auto 28px; padding-bottom: 20px; border-bottom: 1px solid var(--line); }
.fixture-tools p { margin-bottom: 12px; }
.fixture-controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.fixture-controls button, .fixture-controls select { min-height: 44px; }
.fixture-controls select { width: auto; }
#fixture-page { max-width: 1100px; margin: 0 auto; }
#fixture-state { display: block; margin-top: 8px; font-variant-numeric: tabular-nums; }
@media(max-width:600px) { body { padding: 16px; } }
</style>
</head>
<body>
<header class="fixture-tools">
  <p><strong>Isolated UI fixture.</strong> Events and durations below are simulated for visual testing. No model calls. Reduced motion follows the actual browser / operating system preference.</p>
  <div class="fixture-controls">
    <button id="next" type="button">Next stage</button>
    <button id="question" type="button" class="secondary">Check a question</button>
    <button id="restart" type="button" class="secondary">Restart</button>
    <button id="rapid" type="button" class="secondary">Rapid transitions</button>
    <button id="complete" type="button" class="secondary">Complete</button>
    <button id="fail" type="button" class="secondary">Fail</button>
    <button id="tick" type="button" class="secondary">Duration update</button>
    <label>View <select id="mode"><option value="detailed">Detailed</option><option value="simple">Simple</option></select></label>
    <label>Language <select id="language"><option value="en">English</option><option value="zh-CN">中文</option></select></label>
    <button id="theme" type="button" class="secondary">Dark / light</button>
    <a class="button secondary" href="/#content/citation-fixture-content">Citation fixture</a>
  </div>
  <output id="fixture-state" aria-live="polite"></output>
</header>
<main id="fixture-page"></main>
<script type="module">
import {renderGenerationProgress, mountGenerationProgress} from '/static/generation-progress.js';
import {localize} from '/static/i18n.js';
const definitions = [
  ['exploration','searching_sources',12000], ['retrieval','reranking',8000],
  ['planning','planning',4500], ['writing','reviewing',22000],
  ['audio','generating_audio',11000], ['image','generating_image',14000],
  ['video','generating_video',21000], ['saving','saving',1500]
];
const epoch = Date.parse('2026-09-20T12:00:00Z');
let step = 1, status = 'running', tick = 0, checked = 0, mode = 'detailed', controller, rapidTimer;
const page = document.querySelector('#fixture-page');
const motion = matchMedia('(prefers-reduced-motion: reduce)');
function buildJob() {
  let elapsed = 0;
  const events = [];
  const stages = definitions.map(([id, activity, duration], index) => {
    const complete = status === 'succeeded' || index < step;
    const active = index === step && status !== 'succeeded';
    const value = complete ? duration : active ? 2500 + tick : 0;
    if (complete || active) {
      events.push({id:id+'-start',stage:id,code:'stage_started',at:new Date(epoch+elapsed).toISOString(),data:{}});
      events.push({id:id+'-activity',stage:id,code:'activity_changed',at:new Date(epoch+elapsed+300).toISOString(),data:{activity}});
      if (id === 'retrieval') events.push({id:'retrieval-selected',stage:id,code:'retrieval_selected',at:new Date(epoch+elapsed+900).toISOString(),data:{selected:10}});
      if (id === 'exploration') events.push({id:'exploration-search',stage:id,code:'exploration_search',at:new Date(epoch+elapsed+800).toISOString(),data:{round:1,queries:3}});
      if (complete) events.push({id:id+'-end',stage:id,code:'stage_completed',at:new Date(epoch+elapsed+value).toISOString(),data:{}});
    }
    elapsed += value;
    return {id,kind:id,status:complete?'completed':active?(status==='failed'?'failed':'active'):'pending',elapsed_ms:complete||active?value:null,timing_complete:complete||active&&status==='failed'};
  });
  if (status === 'succeeded') events.push({id:'task-complete',stage:'saving',code:'task_succeeded',at:new Date(epoch+elapsed).toISOString(),data:{}});
  if (status === 'failed') events.push({id:'task-failed',stage:definitions[step][0],code:'task_failed',at:new Date(epoch+elapsed).toISOString(),data:{}});
  return {id:'simulated-ui-progress',kind:'generate',status,content_id:status==='succeeded'?'citation-fixture-content':null,error:status==='failed'?'Isolated fixture: simulated provider interruption.':null,timeline:{recorded:true,unit:'questions',total:3,completed:step>3?3:step===3?checked:0,active_stage:status==='succeeded'?null:definitions[step][0],activity:definitions[step][1],elapsed_ms:elapsed,timing_complete:status!=='running',stages,events}};
}
function stateLabel() {
  document.querySelector('#fixture-state').textContent = `Simulated state: ${status} · ${definitions[step][0]} · ${mode} · actual reduced motion: ${motion.matches ? 'on' : 'off'}`;
}
function update() { controller.update(buildJob()); stateLabel(); }
function mount() { controller?.destroy(); const job=buildJob(); page.innerHTML=renderGenerationProgress(job,{mode}); controller=mountGenerationProgress(page.querySelector('[data-generation-progress]'),job,{mode}); stateLabel(); }
function stopRapid() { clearInterval(rapidTimer); rapidTimer=null; }
function advance() { tick=0; if(step<definitions.length-1) step++; else status='succeeded'; update(); }
document.querySelector('#next').addEventListener('click',()=>{stopRapid();if(status==='running')advance();});
document.querySelector('#question').addEventListener('click',()=>{stopRapid();step=3;status='running';checked=Math.min(3,checked+1);update();});
document.querySelector('#restart').addEventListener('click',()=>{stopRapid();step=0;status='running';tick=0;checked=0;update();});
document.querySelector('#rapid').addEventListener('click',()=>{stopRapid();step=0;status='running';tick=0;update();rapidTimer=setInterval(()=>{advance();if(status!=='running')stopRapid();},90);});
document.querySelector('#complete').addEventListener('click',()=>{stopRapid();step=definitions.length-1;status='succeeded';update();});
document.querySelector('#fail').addEventListener('click',()=>{stopRapid();status='failed';update();});
document.querySelector('#tick').addEventListener('click',()=>{if(status==='running'){tick+=1000;update();}});
document.querySelector('#mode').addEventListener('change',event=>{mode=event.target.value;mount();});
document.querySelector('#language').addEventListener('change',event=>{document.documentElement.lang=event.target.value;localize();});
document.querySelector('#theme').addEventListener('click',()=>{document.documentElement.dataset.theme=document.documentElement.dataset.theme==='light'?'dark':'light';});
page.addEventListener('click',event=>{if(event.target.closest('[data-action="open-content"]'))location.href='/#content/citation-fixture-content';});
motion.addEventListener('change',stateLabel);
window.addEventListener('beforeunload',()=>{stopRapid();controller?.destroy();});
mount();
</script>
</body></html>'''


def create_fixture():
    settings = Settings(data_dir=Path(mkdtemp(prefix="lumori-citation-progress-ui-")),
                        auth_cookie_name="lumori_citation_progress_fixture")
    app = create_app(settings)
    record = json.loads((ROOT / "docs/rag/auto-exploration/ml-discovery-20260920/after-en-08.json").read_text())
    sources = deepcopy(record["evidence"]["sources"])
    with TestClient(app) as client:
        response = client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD,
                                                           "display_name": "UI fixture"})
        assert response.status_code == 201, response.text
        session = response.json()
        user_id = session["user"]["id"]
        client.headers.update({"X-CSRF-Token": session["csrf_token"], "X-Account-ID": user_id})
        response = client.post("/api/courses", json={"name": "Machine Learning · isolated UI fixture"})
        assert response.status_code in (200, 201), response.text
        course_id = response.json()["id"]
        original_ids = list(dict.fromkeys(source["document_id"] for source in sources))
        for original_id in original_ids:
            document_sources = [source for source in sources if source["document_id"] == original_id]
            # These are the saved evidence excerpts, not a fabricated full source.
            body = "# Saved source excerpts · UI fixture\n\n" + "\n\n".join(source["text"] for source in document_sources)
            response = client.post("/api/documents", data={"course_id": course_id},
                                   files={"file": (document_sources[0]["document_name"], body.encode())})
            assert response.status_code in (200, 201), response.text
            for source in document_sources:
                source["document_id"] = response.json()["id"]
        timestamp = now()
        config = deepcopy(record["request"])
        config["course_id"] = course_id
        config["ui_fixture"] = True
        store = app.state.store
        with store.connect() as db:
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)",
                       ("citation-fixture-job", "citation-fixture-seed", "generate", dumps(config),
                        "succeeded", dumps({"content_id": CONTENT_ID}), None, timestamp, timestamp))
            db.execute("INSERT INTO job_owners VALUES(?,?)", ("citation-fixture-job", user_id))
            # Approval is only a UI fixture state, never a claim of human review.
            db.execute("INSERT INTO contents VALUES(?,?,?,?,?,?,?,?,?)",
                       (CONTENT_ID, course_id, "citation-fixture-job", 1, "approved", dumps(record["asset"]),
                        dumps(sources), dumps(config), timestamp))
            db.execute("INSERT INTO revisions VALUES(?,?,?,?)", (CONTENT_ID, 1, dumps(record["asset"]), timestamp))
        assert client.get("/api/contents/" + CONTENT_ID).status_code == 200
        assert client.get("/api/learn/" + CONTENT_ID).status_code == 200
        assert not store.all("SELECT id FROM calls"), "UI fixture must not call model providers"

    @app.get("/__ui/progress", response_class=HTMLResponse, include_in_schema=False)
    async def progress_fixture():
        return PROGRESS_HTML

    return app
