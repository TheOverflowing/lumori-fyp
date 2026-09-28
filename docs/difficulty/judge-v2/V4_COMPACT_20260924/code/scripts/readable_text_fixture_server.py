"""Offline layout fixture using the production renderer; no DB or provider calls.

Run: .venv/bin/python -m uvicorn scripts.readable_text_fixture_server:create_fixture --factory --port 8772
Open / for review layout or /?view=learning for the answer-hidden learning layout.
"""
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

SOURCE_ID = 'context_487e8909cb9087ab351d6ca46d06db51'
CLAIMS = (
    'A delivery-robot engineer is designing a learning agent. The robot receives sensor readings, '
    'chooses movement actions, and after each action receives a scalar reward. The engineer makes '
    "the following four claims. Claim 1: The robot's behavior is governed by a policy, which is a "
    'function mapping observations of the environment to actions. Claim 2: Because the robot only '
    'receives a scalar reward after each action, the environment always tells the robot which of its '
    'past actions were optimal. Claim 3: The robot may need to give up some short-term reward to explore '
    'strategies it has not yet tried, rather than always exploiting its currently best-known policy. '
    'Claim 4: If the environment is fully observed, the problem is called a Markov decision process. '
    'Which of the following correctly classifies the four claims according to the reinforcement '
    'learning framework as described in the source material?'
)
NUMBERED = (
    'A team is building a reinforcement learning (RL) agent to control a cleaning robot in a large house. '
    'The robot can only sense what is in its current room, and it receives a small positive reward '
    'whenever its battery is recharged at a charging station. Using only the descriptions below, which '
    'statement is the best analysis of this situation? (1) In RL, an agent interacts with an environment '
    'over a series of time steps: at each step it receives an observation, chooses an action that is '
    'transmitted back to the environment, and then receives a reward; its behavior is governed by a policy, '
    'which is a function mapping observations to actions, and the goal is to produce good policies. '
    '(2) Because the robot only senses its current room, its current observation might not tell it '
    'everything about its current state, so it may have to infer its location by considering earlier '
    'observations — this is the problem of partial observability. (3) When the environment is fully '
    'observed, the RL problem is called a Markov decision process. (4) At any point an RL agent might '
    'know one good policy, but there might be better policies it has never tried, so it must constantly '
    'choose whether to exploit the best currently known strategy or explore the space of strategies, '
    'potentially giving up short-term reward for knowledge.'
)


def create_fixture():
    app = FastAPI()
    app.mount('/static', StaticFiles(directory=Path(__file__).resolve().parents[1] / 'app/static'))

    @app.get('/', response_class=HTMLResponse)
    async def page():
        asset = {'title':'Reinforcement learning practice', 'questions':[
            {'stem':stem, 'options':['The supported statements follow from the observations.', 'More evidence is needed.'],
             'answer':'A', 'explanation':f'First, distinguish observations from rewards. [{SOURCE_ID}]\n\nThen evaluate each claim separately.\nPreserve this authored line break.',
             'citation_ids':[SOURCE_ID]}
            for stem in [CLAIMS,NUMBERED,'机器人满足以下条件：（1）只能观察当前房间的状态。（2）可以参考之前获得的观察。请判断哪种说法正确？\n\n请说明理由，保留关键推理步骤。']
        ]}
        sources = [{'id':SOURCE_ID,'document_name':'UI fixture · sample source','text':'Synthetic source for citation interaction; no model review claim.','page':1}]
        data = json.dumps({'asset':asset,'sources':sources},ensure_ascii=False).replace('<','\\u003c')
        return '''<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Lumori · text layout fixture</title>
<link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/material.css">
<link rel="stylesheet" href="/static/preferences.css"><link rel="stylesheet" href="/static/citations.css">
<link rel="stylesheet" href="/static/content-review.css">
<style>body{padding:28px}main{padding:0;margin:auto;max-width:850px}.fixture-tools{display:flex;align-items:center;gap:16px;margin:0 auto 24px;max-width:850px}.fixture-tools small{margin-right:auto}@media(max-width:600px){body{padding:12px}.document-paper{padding:24px 18px}}</style>
</head><body><header class="fixture-tools"><small>Offline layout fixture · no model calls</small><button id="theme" class="secondary">Dark / light</button><a href="/?view=learning">Learning view</a></header>
<main><article class="document-paper" id="material"></article></main>
<script type="module">
import {renderAsset} from '/static/content-renderer.js';
import {mountCitations} from '/static/citations.js';
const {asset,sources} = ''' + data + ''';
const learning = new URLSearchParams(location.search).get('view') === 'learning';
if(learning) for(const question of asset.questions) { delete question.answer; delete question.explanation; }
const root = document.querySelector('#material');
root.innerHTML = renderAsset(asset,!learning,null,sources);
mountCitations(root,sources,asset);
document.querySelector('#theme').onclick = () => { document.documentElement.dataset.theme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'; };
</script></body></html>'''

    return app
