import test from 'node:test';
import assert from 'node:assert/strict';
import { approvalLabel, approvalLabelKey, bindAiReviewPanel, renderAiReviewPanel } from '../app/static/ai-review.js';

globalThis.document={documentElement:{lang:'zh-CN'}};
const content={id:'c1',version:3,status:'draft',asset:{title:'Lesson'}};
const review={job_id:'r1',version:3,status:'succeeded',decision:'revision_required',summary:'Check the second claim.',checks:[{key:'groundedness',status:'fail',rationale:'Source does not support this claim.'}],items:[{id:'section:1',status:'fail',rationale:'Revise the claim.'}],findings:[{unit_id:'section:1',severity:'error',message:'Unsupported claim.',suggestion:'Use the supported conclusion.',source_ids:['s1']}],applied:false};

test('review approval uses persisted exact-version provenance and stale reports cannot approve',()=>{
  document.documentElement.lang='zh-CN';
  assert.equal(approvalLabel({...content,status:'approved',approval:{method:'ai',version:3}}),'AI 审核通过');
  assert.equal(approvalLabel({...content,status:'approved',approval:{method:'manual',version:3}}),'人工确认');
  assert.equal(approvalLabel({...content,status:'approved',approval:{method:'ai',version:2}}),'已确认');
  assert.equal(approvalLabelKey({...content,status:'approved',approval:{method:'manual',version:3}}),'人工确认');
  const stale=renderAiReviewPanel({...content,ai_review:{...review,version:2,decision:'approve',applied:true}});
  assert.match(stale,/上个版本的审核/);assert.doesNotMatch(stale,/本次审核已自动确认当前版本/);
  const unapplied=renderAiReviewPanel({...content,ai_review:{...review,decision:'approve'}});
  assert.match(unapplied,/AI 建议通过/);assert.doesNotMatch(unapplied,/本次审核已自动确认当前版本/);
});

test('reports retain rationale and safe source text without rendering authored HTML',()=>{
  const attack='<img src=x onerror=alert(1)>', html=renderAiReviewPanel({...content,ai_review:{...review,summary:attack,model:attack,checks:[{key:attack,status:attack,rationale:attack}],items:[{id:attack,status:'pass',rationale:attack}],findings:[{unit_id:attack,severity:attack,message:attack,suggestion:attack,source_ids:[attack]}]}});
  assert.doesNotMatch(html,/<img src=x|data-result="<|<script|href=/);
  assert.match(html,/&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html,/data-result="uncertain"/);
  assert.match(html,/AI 审核不等同于教师确认/);
  assert.match(html,/<details class="ai-review-evidence" data-ai-review-disclosure="evidence"><summary>/);
});

test('English UI translates checks and actions while preserving report text',()=>{
  document.documentElement.lang='en';
  const html=renderAiReviewPanel({...content,ai_review:review});
  assert.match(html,/Changes recommended/);assert.match(html,/Run AI review again/);
  assert.match(html,/Source does not support this claim/);
  assert.match(html,/AI review is not teacher confirmation/);
  document.documentElement.lang='zh-CN';
});

test('unexpected enum values remain plain text without using inherited object keys',()=>{
  const html=renderAiReviewPanel({...content,ai_review:{...review,checks:[{key:'__proto__',status:'constructor',rationale:'Unknown'}],findings:[{severity:'toString',quote:'<script>quote</script>',message:'Unknown'}]}});
  assert.match(html,/__proto__/);assert.match(html,/data-result="uncertain"/);
  assert.match(html,/&lt;script&gt;quote&lt;\/script&gt;/);assert.doesNotMatch(html,/<script>/);
});

test('approved materials keep review and provenance but no manual start action',()=>{
  const html=renderAiReviewPanel({...content,status:'approved',approval:{method:'ai',version:3},ai_review:{...review,decision:'approve',applied:true}});
  assert.match(html,/本次审核已自动确认当前版本/);assert.match(html,/ai-review-provenance/);
  assert.match(html,/Source does not support this claim/);assert.doesNotMatch(html,/data-ai-review-start/);
  for (const status of ['failed','cancelled']) {
    assert.match(renderAiReviewPanel({...content,ai_review:{...review,status}}),/本次审核未自动确认材料/);
  }
});

class Visibility extends EventTarget { hidden=false; }
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
async function tick(context,ms=0){context.mock.timers.tick(ms);for(let i=0;i<6;i++)await Promise.resolve();}
function harness(options={}) {
  const listeners={}, body={markup:'',details:[],get innerHTML(){return this.markup;},set innerHTML(value){this.markup=value;this.details=[...value.matchAll(/data-ai-review-disclosure="([^"]+)"/g)].map(match=>({dataset:{aiReviewDisclosure:match[1]},open:false}));},querySelector(){return null;},querySelectorAll(){return this.details;}}, live={dataset:{}}, control={closest(){return this;}};
  const panel={dataset:{},isConnected:true,matches(){return true;},contains(node){return node===control;},querySelector(selector){return {'[data-ai-review-body]':body,'[data-ai-review-live]':live}[selector];},addEventListener(type,fn){listeners[type]=fn;},removeEventListener(type,fn){if(listeners[type]===fn)delete listeners[type];}};
  const updates=[],errors=[],visibility=new Visibility();let keys=0,editing=false;
  const dispose=bindAiReviewPanel(panel,options.content || content,{start:async()=>({job_id:'r1'}),load:async()=>content,onUpdated:next=>updates.push(next),onError:cause=>errors.push(cause),visibility,interval:100,makeKey:()=>`key-${++keys}`,isEditing:()=>editing,...options});
  return {body,panel,live,updates,errors,dispose,visibility,send:()=>listeners.click?.({target:control,preventDefault(){}}),edit(value){editing=value;dispose.refresh();}};
}

test('transport retries reuse request key and never claim that failure changed approval',async()=>{
  const payloads=[],view=harness({start:async payload=>{payloads.push(payload);throw new Error('Connection interrupted');}});
  await view.send();view.dispose.refresh();view.dispose.refresh({...content});await view.send();
  assert.equal(payloads.length,2);assert.deepEqual(payloads[0],{version:3,request_key:'key-1'});
  assert.equal(payloads[1].request_key,payloads[0].request_key);assert.equal(view.updates.length,0);
  assert.match(view.body.innerHTML,/暂时无法连接审核服务/);assert.match(view.body.innerHTML,/重试提交审核/);
  assert.doesNotMatch(view.body.innerHTML,/data-ai-review-start disabled/);view.dispose();
});

test('review runs once while pending and disposal aborts the request and ignores late success',async()=>{
  const pending=deferred();let calls=0,signal,loads=0;
  const view=harness({start:(payload,options)=>{calls++;signal=options.signal;return pending.promise;},load:async()=>{loads++;return content;}});
  const sending=view.send();await view.send();assert.equal(calls,1);assert.match(view.body.innerHTML,/data-ai-review-start disabled/);
  view.dispose();assert.equal(signal.aborted,true);pending.resolve({job_id:'r1'});await sending;
  assert.equal(loads,0);assert.equal(view.updates.length,0);assert.equal(view.errors.length,0);
});

test('unsaved editing blocks review and refresh updates only the panel state',async()=>{
  let calls=0;const view=harness({start:async()=>{calls++;throw new Error('Offline');}});
  view.edit(true);await view.send();assert.equal(calls,0);assert.match(view.body.innerHTML,/请先保存或收起编辑/);
  view.edit(false);await view.send();assert.equal(calls,1);view.dispose();
});

test('existing running review resumes polling, applies current approval, and stops on completion',async context=>{
  context.mock.timers.enable({apis:['setTimeout']});
  let loads=0;const approved={...content,status:'approved',approval:{method:'ai',version:3},ai_review:{...review,decision:'approve',applied:true}};
  const view=harness({content:{...content,ai_review:{...review,status:'running'}},load:async()=>{loads++;return approved;}});context.after(view.dispose);
  await tick(context,100);assert.equal(loads,1);assert.deepEqual(view.updates,[approved]);
  assert.match(view.body.innerHTML,/本次审核已自动确认当前版本/);assert.doesNotMatch(view.body.innerHTML,/data-ai-review-start/);
  await tick(context,1000);assert.equal(loads,1);
});

test('a newer server version never replaces the current editor through onUpdated',async context=>{
  context.mock.timers.enable({apis:['setTimeout']});let loads=0;
  const view=harness({content:{...content,ai_review:{...review,status:'running'}},load:async()=>{loads++;return {...content,version:4};}});context.after(view.dispose);
  await tick(context,100);assert.equal(view.updates.length,0);assert.match(view.body.innerHTML,/材料已有新版本/);
  assert.match(view.body.innerHTML,/data-ai-review-start disabled/);await tick(context,1000);assert.equal(loads,1);
});

test('refreshing to a newly saved version aborts and ignores an older submission',async()=>{
  const pending=deferred();let signal;const payloads=[];
  const view=harness({start:(payload,options)=>{payloads.push(payload);signal=options.signal;return pending.promise;}});
  const sending=view.send();view.dispose.refresh({...content,version:4});assert.equal(signal.aborted,true);
  pending.resolve({job_id:'old-job'});await sending;assert.equal(view.updates.length,0);assert.doesNotMatch(view.body.innerHTML,/AI 审核排队中/);
  view.dispose();
});

test('disposing a background read aborts it and suppresses late updates and errors',async context=>{
  context.mock.timers.enable({apis:['setTimeout']});const pending=deferred();let signal;
  const view=harness({content:{...content,ai_review:{...review,status:'running'}},load:options=>{signal=options.signal;return pending.promise;}});
  await tick(context,100);view.dispose();assert.equal(signal.aborted,true);
  pending.reject(new Error('Old response'));await tick(context);assert.equal(view.errors.length,0);assert.equal(view.updates.length,0);
});

test('a polling error recovers without creating another review request',async context=>{
  context.mock.timers.enable({apis:['setTimeout']});let loads=0,starts=0;
  const active={...content,ai_review:{...review,status:'running'}};
  const view=harness({content:active,start:async()=>{starts++;},load:async()=>{if(++loads===1)throw new Error('Offline');return active;}});context.after(view.dispose);
  await tick(context,100);assert.match(view.body.innerHTML,/暂时无法连接审核服务/);
  await tick(context,100);assert.doesNotMatch(view.body.innerHTML,/暂时无法连接审核服务/);assert.equal(starts,0);
});

test('backend failures show their reason as escaped and localized copy',()=>{
  const error='AI 审核返回的结构、覆盖范围或引用无效，未自动确认。';
  document.documentElement.lang='en';
  const html=renderAiReviewPanel({...content,ai_review:{version:3,status:'failed',error}});
  assert.match(html,/review response has invalid structure, coverage, or references/);
  assert.match(html,/class="ai-review-error ai-review-backend-error" role="alert"/);
  const unsafe=renderAiReviewPanel({...content,ai_review:{version:3,status:'cancelled',error:'<script>reason</script>'}});
  assert.match(unsafe,/&lt;script&gt;reason&lt;\/script&gt;/);assert.doesNotMatch(unsafe,/<script>/);
  document.documentElement.lang='zh-CN';
});

test('known submission errors retain actionable API reasons without leaking arbitrary stacks',async()=>{
  const cause=Object.assign(new Error('Internal error'),{uiMessage:{key:'内容已更新，请刷新后重新审核。'}});
  const view=harness({start:async()=>{throw cause;}});await view.send();
  assert.match(view.body.innerHTML,/内容已更新，请刷新后重新审核/);assert.doesNotMatch(view.body.innerHTML,/Internal error/);view.dispose();
});

test('review evidence is collapsed, summaries stay visible, and internal IDs become human labels',()=>{
  const html=renderAiReviewPanel({...content,sources:[{id:'private-source-id',document_name:'Lecture <one>.pdf',page:7}],ai_review:{...review,items:[{id:'section:1',status:'pass',rationale:'Supported.'},{id:'question:2',status:'pass',rationale:'Supported.'}],findings:[{unit_id:'global',severity:'error',message:'Important finding.',suggestion:'Correct this.',source_ids:['private-source-id','unknown-private-id']}]}});
  assert.match(html,/小节 1/);assert.match(html,/第 2 题/);assert.match(html,/整体材料/);
  assert.match(html,/Lecture &lt;one&gt;\.pdf/);assert.match(html,/第 7 页/);assert.match(html,/来源信息不可用/);
  assert.doesNotMatch(html,/private-source-id|unknown-private-id|section:1|question:2/);
  const details=html.indexOf('<details class="ai-review-evidence"');
  assert.ok(html.indexOf('Check the second claim.')<details);assert.ok(html.indexOf('Important finding.')<details);
  assert.ok(html.indexOf('Source does not support this claim.')>details);
  assert.doesNotMatch(html,/<details[^>]*\bopen(?:\s|=|>)/);
});

test('expanded evidence survives panel updates and state changes are announced politely',()=>{
  const view=harness({content:{...content,ai_review:review}});
  view.body.details.find(node=>node.dataset.aiReviewDisclosure==='evidence').open=true;
  view.dispose.refresh({...content,ai_review:{...review,summary:'Updated review summary.'}});
  assert.equal(view.body.details.find(node=>node.dataset.aiReviewDisclosure==='evidence').open,true);
  assert.equal(view.live.dataset.i18n,'建议修改后再审核');
  view.dispose.refresh({...content,ai_review:{...review,decision:'human_review'}});
  assert.equal(view.live.dataset.i18n,'需要人工判断');
  const html=renderAiReviewPanel(content);
  assert.match(html,/data-ai-review-live role="status" aria-live="polite" aria-atomic="true"/);view.dispose();
});

test('high priority findings appear first and additional findings remain accessible in a disclosure',()=>{
  const findings=['uncertain','error','error','uncertain'].map((severity,index)=>({unit_id:'global',severity,message:`Finding number ${index}`,suggestion:'Verify.'}));
  const html=renderAiReviewPanel({...content,ai_review:{...review,findings}});
  assert.ok(html.indexOf('Finding number 1')<html.indexOf('Finding number 0'));
  assert.match(html,/查看其余 1 项问题/);assert.match(html,/data-ai-review-disclosure="more-findings"/);
  assert.deepEqual(findings.map(row=>row.severity),['uncertain','error','error','uncertain']);
});
