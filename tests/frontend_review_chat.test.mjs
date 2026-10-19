import test from 'node:test';
import assert from 'node:assert/strict';
import { bindReviewChat, renderReviewChat, renderReviewChatMessages } from '../app/static/review-chat.js';

globalThis.document={documentElement:{lang:'zh-CN'}};
const content={id:'c1',version:3,status:'draft',asset:{questions:[{slot_id:'q1',stem:'First'},{slot_id:'q2',stem:'Second'}]}};
const empty={version:3,messages:[],active_job_id:null};
const revision={id:'a1',role:'assistant',text:'已补充推导过程。',version:4,action:'explanation',slot_id:'q2',can_undo:true,changes:[{field:'explanation',before:'Old explanation',after:'New explanation'}]};
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const flush=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};
class Element {
  dataset={};listeners={};value='';disabled=false;hidden=false;scrollTop=0;scrollHeight=100;clientHeight=100;details=[];markup='';attributes={};
  set innerHTML(value){this.markup=value;this.details=[...value.matchAll(/data-chat-comparison="([^"]+)"/g)].map(match=>({dataset:{chatComparison:match[1]},open:false}));}
  get innerHTML(){return this.markup;}
  querySelectorAll(){return this.details;}
  addEventListener(type,fn){this.listeners[type]=fn;}
  removeEventListener(type,fn){if(this.listeners[type]===fn)delete this.listeners[type];}
  setAttribute(key,value){this.attributes[key]=value;}
  focus(){this.focused=true;}
  emit(type,event={}){return this.listeners[type]?.({preventDefault(){},...event});}
}
class Visibility extends EventTarget {hidden=false;}
function harness(options={}) {
  const names=['log','input','question','form','send','status','error','error-text','reload','disclosure'];
  const nodes=Object.fromEntries(names.map(name=>[name,new Element()]));
  const panel=new Element();panel.isConnected=true;panel.matches=()=>true;panel.querySelector=selector=>nodes[selector.slice(11,-1)];panel.contains=()=>true;panel.scrollIntoView=()=>{};
  const visibility=new Visibility();let editing=false,keys=0;
  const updates=[],payloads=[],undos=[];
  const dispose=bindReviewChat(panel,content,{visibility,interval:100,makeKey:()=>`key-${++keys}`,isEditing:()=>editing,load:async()=>empty,send:async body=>{payloads.push(body);return {job_id:'j1'};},undo:async body=>{undos.push(body);return {version:5};},onContentUpdated:async next=>{updates.push(next);return {...content,version:next.version};},...options});
  nodes.form.requestSubmit=()=>nodes.form.emit('submit');
  const click=(selector,dataset={})=>panel.emit('click',{target:{dataset,closest:query=>query===selector?{dataset}:null}});
  return {nodes,panel,visibility,dispose,updates,payloads,undos,type(value){nodes.input.value=value;nodes.input.emit('input');},submit:()=>nodes.form.emit('submit'),undo:id=>click('[data-chat-undo]',{chatUndo:id}),reload:()=>click('[data-chat-reload]'),edit(value){editing=value;dispose.refresh();}};
}

test('sidebar localizes controls, retains authored text, and escapes messages and comparisons',()=>{
  document.documentElement.lang='en';
  const html=renderReviewChat(content);
  assert.match(html,/Revision assistant/);assert.match(html,/Whole material/);assert.match(html,/Question 2/);assert.match(html,/aria-label="Conversation"/);assert.match(html,/maxlength="2000"/);
  const attack='<img src=x onerror=alert(1)>', messages=renderReviewChatMessages([{...revision,id:'a"1',text:attack,changes:[{field:'options',before:[attack],after:['<script>unsafe</script>']}]}],{version:4});
  assert.doesNotMatch(messages,/<img src=x|<script>/);assert.match(messages,/&lt;img/);assert.match(messages,/Compare changes/);assert.match(messages,/data-chat-undo="a&quot;1"/);assert.match(messages,/Undo this change/);
  document.documentElement.lang='zh-CN';
});

test('undo is restricted to the latest eligible message on the displayed version',()=>{
  const messages=[{...revision,id:'old',version:3},{...revision,id:'earlier'},{...revision,id:'latest'}];
  const html=renderReviewChatMessages(messages,{version:4});
  assert.equal((html.match(/data-chat-undo=/g)||[]).length,1);assert.match(html,/data-chat-undo="latest"/);
  assert.doesNotMatch(renderReviewChatMessages(messages,{version:5}),/data-chat-undo=/);
  assert.match(renderReviewChatMessages(messages,{version:4,editing:true}),/data-chat-undo="latest" disabled/);
});

test('system undo results and structured diff labels localize while authored replies stay intact',()=>{
  document.documentElement.lang='en';
  const html=renderReviewChatMessages([
    {id:'undo',role:'assistant',action:'undo',text:'已撤销上一次修改。',version:4},
    {...revision,text:'这句模型回答保持中文。',changes:[{field:'citation_ids',before:['source-1'],after:['source-2']},{field:'difficulty',before:'easy',after:'hard'}]},
  ],{version:4});
  assert.match(html,/>The last change has been undone\.</);assert.match(html,/>Cited sources</);assert.match(html,/>Easy</);assert.match(html,/>Hard</);
  assert.match(html,/这句模型回答保持中文。/);assert.doesNotMatch(html,/>已撤销上一次修改。</);assert.doesNotMatch(html,/>citation_ids</);
  document.documentElement.lang='zh-CN';
  const zh=renderReviewChatMessages([{...revision,changes:[{field:'difficulty',before:'medium',after:'easy'}]}],{version:4});
  assert.match(zh,/>中等</);assert.match(zh,/>简单</);
});

test('initial history load blocks submissions, reports failure and recovers by reconnecting',async()=>{
  const initial=deferred();let loads=0;
  const view=harness({load:()=>++loads===1?initial.promise:Promise.resolve(empty)});
  view.type('为什么这题需要修改？');await view.submit();assert.equal(view.payloads.length,0);assert.equal(view.dispose.isBusy(),true);
  initial.reject(new Error('Offline'));await flush();assert.equal(view.nodes.reload.hidden,false);assert.match(view.nodes['error-text'].textContent,/重新连接/);assert.equal(view.nodes.send.disabled,true);
  await view.reload();assert.equal(view.nodes.error.hidden,true);assert.equal(view.nodes.send.disabled,false);view.dispose();
});

test('transport retries preserve the submitted message and reuse its request key',async()=>{
  const payloads=[];const view=harness({send:async body=>{payloads.push(body);throw new Error('Offline');}});
  await flush();view.dispose.selectQuestion('q2');view.type('只把解析写详细一点');await view.submit();await view.submit();
  assert.equal(view.nodes.input.value,'只把解析写详细一点');assert.equal(payloads.length,2);
  assert.deepEqual(payloads[0],{version:3,message:'只把解析写详细一点',slot_id:'q2',auto_review:false,request_key:'key-1'});assert.equal(payloads[1].request_key,'key-1');
  view.type('把解析再写详细一点');await view.submit();assert.equal(payloads[2].request_key,'key-2');view.dispose();
});

test('a sending request runs once, allows drafting, and keeps later typed text when accepted',async()=>{
  const request=deferred();let starts=0,loads=0;
  const view=harness({send:()=>{starts++;return request.promise;},load:async()=>++loads===1?empty:{...empty,active_job_id:'j1',messages:[{id:'u1',role:'user',text:'改写第二题',version:3}]}});
  await flush();view.type('改写第二题');const sending=view.submit();await view.submit();assert.equal(starts,1);assert.equal(view.nodes.input.disabled,false);
  view.type('解析也详细一点');request.resolve({job_id:'j1'});await sending;
  assert.equal(view.nodes.input.value,'解析也详细一点');assert.equal(view.nodes.send.disabled,true);assert.match(view.nodes.status.textContent,/正在处理/);assert.match(view.nodes.log.innerHTML,/改写第二题/);view.dispose();
});

test('saved revisions refresh the document before a follow-up uses its new version',async()=>{
  let loads=0;const payloads=[];
  const view=harness({load:async()=>++loads===1?empty:{version:4,active_job_id:null,messages:[revision]},send:async body=>{payloads.push(body);return {job_id:'j1'};},getAutoReview:()=>true});
  await flush();view.dispose.selectQuestion('q2');view.type('仅修改解析');await view.submit();assert.equal(view.updates.length,1);assert.equal(view.nodes.input.value,'');assert.match(view.nodes.log.innerHTML,/New explanation/);
  view.type('再简单一点');await view.submit();assert.equal(payloads[1].version,4);assert.equal(payloads[1].slot_id,'q2');assert.equal(payloads[1].auto_review,true);view.dispose();
});

test('answer-only turns leave the material version untouched and do not offer undo',async()=>{
  let loads=0;const view=harness({load:async()=>++loads===1?empty:{...empty,messages:[{id:'a1',role:'assistant',action:'answer',text:'因为这里缺少条件。',version:3}]}});
  await flush();view.type('为什么这题有问题？');await view.submit();assert.equal(view.updates.length,0);assert.doesNotMatch(view.nodes.log.innerHTML,/data-chat-undo/);view.dispose();
});

test('undo persists a new version, keeps history and retries with one key after a transport failure',async()=>{
  const payloads=[];let undone=false,loads=0;
  const view=harness({load:async()=>{loads++;return undone?{version:5,active_job_id:null,messages:[{...revision,can_undo:false},{id:'undo',role:'assistant',text:'已撤销',action:'undo',version:5}]}:{version:4,active_job_id:null,messages:[revision]};},undo:async body=>{payloads.push(body);if(payloads.length===1)throw new Error('Offline');undone=true;return {version:5};}});
  await flush();await view.undo('a1');assert.match(view.nodes['error-text'].textContent,/撤销未完成/);await view.undo('a1');
  assert.equal(payloads.length,2);assert.deepEqual(payloads[0],{version:4,message_id:'a1',request_key:'key-1'});assert.equal(payloads[1].request_key,'key-1');assert.equal(view.updates.at(-1).version,5);assert.match(view.nodes.log.innerHTML,/已撤销/);assert.doesNotMatch(view.nodes.log.innerHTML,/data-chat-undo/);view.dispose();
});

test('unsaved edits prevent send and undo without discarding a typed message',async()=>{
  const view=harness({load:async()=>({version:3,active_job_id:null,messages:[{...revision,version:3}]})});
  await flush();view.type('把本题改简单一点');view.edit(true);await view.submit();await view.undo('a1');
  assert.equal(view.payloads.length,0);assert.equal(view.undos.length,0);assert.match(view.nodes.status.textContent,/保存或丢弃/);assert.equal(view.nodes.input.value,'把本题改简单一点');
  view.edit(false);assert.equal(view.nodes.send.disabled,false);view.dispose();
});

test('a saved version arriving during an edit waits until the draft is cleared',async()=>{
  const pending=deferred();const view=harness({load:()=>pending.promise});view.edit(true);
  pending.resolve({version:4,active_job_id:null,messages:[revision]});await flush();assert.equal(view.updates.length,0);assert.equal(view.nodes.send.disabled,true);
  view.edit(false);await flush();assert.equal(view.updates.length,1);view.dispose();
});

test('existing jobs resume polling and finish without replacing the composer or expanded comparison',async context=>{
  context.mock.timers.enable({apis:['setTimeout']});let loads=0;
  const view=harness({load:async()=>++loads===1?{...empty,active_job_id:'j1',messages:[{...revision,version:3,can_undo:false}]}:{version:4,active_job_id:null,messages:[revision]}});context.after(view.dispose);
  await flush();view.type('下一条草稿');view.nodes.log.details[0].open=true;view.nodes.log.scrollHeight=700;view.nodes.log.clientHeight=200;view.nodes.log.scrollTop=100;
  context.mock.timers.tick(100);await flush();assert.equal(loads,2);assert.equal(view.nodes.input.value,'下一条草稿');assert.equal(view.nodes.log.details[0].open,true);assert.equal(view.nodes.log.scrollTop,100);assert.equal(view.dispose.isBusy(),false);
  context.mock.timers.tick(1000);await flush();assert.equal(loads,2);
});

test('disposal aborts history and submission requests and ignores late success',async()=>{
  const history=deferred();let signal;const view=harness({load:({signal:next})=>{signal=next;return history.promise;}});
  view.dispose();assert.equal(signal.aborted,true);history.resolve({version:4,active_job_id:null,messages:[revision]});await flush();assert.equal(view.updates.length,0);
  const request=deferred();const other=harness({send:(_,options)=>{signal=options.signal;return request.promise;}});
  await flush();other.type('修改第二题');const sending=other.submit();other.dispose();assert.equal(signal.aborted,true);request.resolve({job_id:'late'});await sending;assert.equal(other.updates.length,0);assert.equal(other.nodes.input.value,'修改第二题');
});

test('Enter submits only outside IME composition and Shift+Enter retains a newline',async()=>{
  const view=harness();await flush();view.type('为什么？');let submits=0,prevented=0;view.nodes.form.requestSubmit=()=>submits++;
  for (const event of [{key:'Enter',isComposing:true},{key:'Enter',keyCode:229},{key:'Enter',shiftKey:true}])view.nodes.input.emit('keydown',{...event,preventDefault(){prevented++;}});
  assert.equal(submits,0);assert.equal(prevented,0);
  view.nodes.input.emit('keydown',{key:'Enter',preventDefault(){prevented++;}});assert.equal(submits,1);assert.equal(prevented,1);view.dispose();
});
