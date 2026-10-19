import test from 'node:test';
import assert from 'node:assert/strict';
import {createSessionClient} from '../app/static/auth.js';
import {readSessionBootstrap,sessionChangeRequiresReset} from '../app/static/session-bootstrap.js';

test('server-provided identity initializes the workspace without a status request',async()=>{
  const calls=[],seen=[];let removed=false;
  const user={id:'demo',email:'demo@example.test'};
  const data={user,csrf_token:'page-csrf'};
  const c=createSessionClient({onSession:s=>seen.push(s),fetchImpl:async(url,opts)=>{calls.push({url,opts});return {ok:true,json:async()=>[]};}});
  const boot=readSessionBootstrap({getElementById:()=>({textContent:JSON.stringify(data),remove:()=>removed=true})});
  c.initialize(boot);
  assert.equal(calls.length,0);assert.equal(seen.at(-1).user.id,'demo');assert.ok(removed);
  await c.request('/courses');
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/courses');
  assert.equal(calls[0].opts.headers['X-Account-ID'],'demo');
});

test('anonymous and unreadable bootstrap opens the normal login flow without a request',()=>{
  for(const raw of ['{"user":null,"csrf_token":null}','broken']){
    const c=createSessionClient({fetchImpl:()=>assert.fail('No background session request')});
    c.initialize(readSessionBootstrap({getElementById:()=>({textContent:raw,remove(){}})}));
    assert.equal(c.session.user,null);
  }
});

test('explicit account switching still clears old account data',()=>{
  assert.equal(sessionChangeRequiresReset(JSON.stringify({userId:'demo'}),'demo'),false);
  for(const value of [JSON.stringify({userId:'other'}),JSON.stringify({userId:null}),'legacy'])
    assert.equal(sessionChangeRequiresReset(value,'demo'),true);
});
