import test from 'node:test';
import assert from 'node:assert/strict';
import {createGenerationPreferences, generationPreferencesKey} from '../app/static/generation-preferences.js';
import {renderSettings, renderSwitch, renderModelConnections} from '../app/static/settings.js';
import {createGenerationFlow} from '../app/static/clarification.js';

globalThis.document={documentElement:{lang:'zh-CN'}};
const memoryStorage=()=>{const values=new Map();return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};};

test('progress view migrates old preferences, stays account-scoped, and preserves fusion',()=>{
  const storage=memoryStorage();
  storage.setItem(generationPreferencesKey('a'),'{"query_fusion":true}');
  const preferences=createGenerationPreferences({storage});
  preferences.setAccount('a');
  assert.equal(preferences.progressMode,'detailed');
  preferences.setProgressMode('simple');
  assert.deepEqual(preferences.requestFields(),{query_fusion:true,auto_review:true});
  preferences.setQueryFusion(false);
  assert.equal(JSON.parse(storage.getItem(generationPreferencesKey('a'))).progress_mode,'simple');
  preferences.setAccount('b');assert.equal(preferences.progressMode,'detailed');
  preferences.setAccount('a');assert.equal(preferences.progressMode,'simple');
  preferences.setAccount(null);assert.equal(preferences.progressMode,'detailed');
  preferences.setProgressMode('simple');assert.equal(preferences.progressMode,'detailed');
});

test('display-only changes are distinguishable and never enter generation requests',()=>{
  const storage=memoryStorage(),changes=[];
  const preferences=createGenerationPreferences({storage,onChange:c=>changes.push(c)});
  preferences.setAccount('a');
  preferences.setProgressMode('simple');
  assert.deepEqual(changes[0].changed,['progressMode']);
  assert.deepEqual(preferences.requestFields(),{auto_review:true});
  preferences.setProgressMode('unknown');assert.equal(changes.length,1);
  storage.setItem(generationPreferencesKey('a'),'{"progress_mode":"detailed"}');
  preferences.syncStorage(generationPreferencesKey('a'));
  assert.equal(preferences.progressMode,'detailed');
  assert.deepEqual(changes[1].changed,['progressMode']);
  preferences.setQueryFusion(true);assert.deepEqual(changes[2].changed,['queryFusion']);
});

test('settings exposes native bilingual progress choices and the selected view',()=>{
  const html=renderSettings(false,'simple');
  assert.match(html,/<legend>.*进度显示/);
  assert.match(html,/type="radio" name="progress-mode" value="simple" checked/);
  assert.doesNotMatch(html,/value="detailed" checked/);
  try {
    document.documentElement.lang='en';
    const english=renderSettings(false,'detailed');
    assert.match(english,/>Progress view</);
    assert.match(english,/>Simple</);
    assert.match(english,/>Detailed</);
  } finally {document.documentElement.lang='zh-CN';}
});

test('fusion defaults off and restores per account without a shared fallback',()=>{
  const storage=memoryStorage(), changes=[];
  storage.setItem('zhixu.query_fusion','true');
  const preferences=createGenerationPreferences({storage,onChange:change=>changes.push(change)});
  assert.deepEqual(preferences.requestFields(),{});
  preferences.setQueryFusion(true);assert.equal(preferences.queryFusion,false);
  preferences.setAccount('account/a');assert.equal(preferences.queryFusion,false);
  preferences.setQueryFusion(true);assert.deepEqual(preferences.requestFields(),{query_fusion:true,auto_review:true});
  preferences.setAccount('account/b');assert.equal(preferences.queryFusion,false);
  preferences.setAccount('account/a');assert.equal(preferences.queryFusion,true);
  assert.match(generationPreferencesKey('account/a'),/account%2Fa/);
  assert.equal(changes.length,1);
  assert.equal(JSON.parse(storage.getItem(generationPreferencesKey('account/a'))).query_fusion,true);
  preferences.setAccount(null);assert.deepEqual(preferences.requestFields(),{});
});

test('new signed-in accounts default agents and review on without a signed-out preference',()=>{
  const storage=memoryStorage(), preferences=createGenerationPreferences({storage});
  preferences.setUseSubagents(true);preferences.setAutoReview(true);
  assert.equal(preferences.useSubagents,false);assert.equal(preferences.autoReview,false);
  assert.deepEqual(preferences.requestFields('quiz'),{});
  assert.equal(storage.getItem(generationPreferencesKey('a')),null);
  preferences.setAccount('a');
  assert.deepEqual(preferences.requestFields('quiz'),{auto_review:true,use_subagents:true});
  assert.deepEqual(preferences.requestFields('assignment'),{auto_review:true,use_subagents:true});
  assert.deepEqual(preferences.requestFields('lesson'),{auto_review:true});
  assert.equal(preferences.queryFusion,false);assert.equal(preferences.autoExplore,false);
  assert.equal(preferences.progressMode,'detailed');
  const saved=JSON.parse(storage.getItem(generationPreferencesKey('a')));
  assert.equal(saved.agent_review_defaults_version,1);
  assert.equal(saved.use_subagents,true);assert.equal(saved.auto_review,true);
  preferences.setAccount(null);
  assert.equal(preferences.useSubagents,false);assert.equal(preferences.autoReview,false);
  assert.deepEqual(preferences.requestFields('lesson'),{});
});

test('legacy false values migrate once without changing fusion, exploration or progress settings',()=>{
  const storage=memoryStorage(), key=generationPreferencesKey('legacy/account');
  storage.setItem(key,JSON.stringify({query_fusion:true,auto_explore:true,progress_mode:'simple',use_subagents:false,auto_review:false}));
  const preferences=createGenerationPreferences({storage});preferences.setAccount('legacy/account');
  assert.equal(preferences.useSubagents,true);assert.equal(preferences.autoReview,true);
  assert.equal(preferences.queryFusion,true);assert.equal(preferences.autoExplore,true);assert.equal(preferences.progressMode,'simple');
  const migrated=JSON.parse(storage.getItem(key));
  assert.equal(migrated.agent_review_defaults_version,1);
  assert.equal(migrated.query_fusion,true);assert.equal(migrated.auto_explore,true);assert.equal(migrated.progress_mode,'simple');
  preferences.setUseSubagents(false);preferences.setAutoReview(false);
  preferences.setAccount('other');assert.equal(preferences.useSubagents,true);assert.equal(preferences.autoReview,true);
  preferences.setAccount('legacy/account');assert.equal(preferences.useSubagents,false);assert.equal(preferences.autoReview,false);
  const reload=createGenerationPreferences({storage});reload.setAccount('legacy/account');
  assert.deepEqual(reload.requestFields('quiz'),{query_fusion:true,auto_explore:true,use_subagents:false});
  assert.equal(reload.autoReview,false);assert.equal(reload.progressMode,'simple');
});

test('per-question opt-out is account-scoped and included only for quiz or assignment',()=>{
  const storage=memoryStorage(), changes=[];
  const preferences=createGenerationPreferences({storage,onChange:change=>changes.push(change)});
  preferences.setAccount('a');preferences.setUseSubagents(false);
  assert.deepEqual(preferences.requestFields('quiz'),{auto_review:true,use_subagents:false});
  assert.deepEqual(preferences.requestFields('assignment'),{auto_review:true,use_subagents:false});
  assert.deepEqual(preferences.requestFields('lesson'),{auto_review:true});
  assert.deepEqual(changes[0].changed,['useSubagents']);
  preferences.setAccount('b');assert.equal(preferences.useSubagents,true);
  preferences.setAccount('a');assert.equal(preferences.useSubagents,false);
  assert.equal(JSON.parse(storage.getItem(generationPreferencesKey('a'))).use_subagents,false);
});

test('automatic review opt-out persists per account and covers every material type',()=>{
  const storage=memoryStorage(), changes=[];
  storage.setItem('zhixu.auto_review','true');
  const preferences=createGenerationPreferences({storage,onChange:change=>changes.push(change)});
  preferences.setAccount('a');
  for(const material of ['lesson','quiz','assignment'])assert.equal(preferences.requestFields(material).auto_review,true);
  preferences.setAutoReview(false);
  for(const material of ['lesson','quiz','assignment'])assert.equal(Object.hasOwn(preferences.requestFields(material),'auto_review'),false);
  assert.deepEqual(changes[0].changed,['autoReview']);assert.equal(changes[0].autoReview,false);
  assert.equal(JSON.parse(storage.getItem(generationPreferencesKey('a'))).auto_review,false);
  const reloaded=createGenerationPreferences({storage});
  reloaded.setAccount('a');assert.equal(reloaded.autoReview,false);
  preferences.setAccount('b');assert.equal(preferences.autoReview,true);
  preferences.setAccount('a');assert.equal(preferences.autoReview,false);
  preferences.setAutoReview(true);assert.equal(JSON.parse(storage.getItem(generationPreferencesKey('a'))).auto_review,true);
  preferences.setAccount(null);assert.equal(preferences.autoReview,false);
});

test('current-version storage synchronization accepts only booleans from the active account',()=>{
  const storage=memoryStorage(), changes=[];
  const preferences=createGenerationPreferences({storage,onChange:change=>changes.push(change)});
  preferences.setAccount('a');
  const record=values=>JSON.stringify({agent_review_defaults_version:1,use_subagents:true,auto_review:true,...values});
  storage.setItem(generationPreferencesKey('b'),record({auto_review:false}));
  preferences.syncStorage(generationPreferencesKey('b'));
  assert.equal(preferences.autoReview,true);assert.equal(changes.length,0);
  storage.setItem(generationPreferencesKey('a'),record({auto_review:false}));
  preferences.syncStorage(generationPreferencesKey('a'));
  assert.equal(preferences.autoReview,false);assert.deepEqual(changes[0].changed,['autoReview']);
  preferences.syncStorage(generationPreferencesKey('a'));assert.equal(changes.length,1);
  for(const value of ['true',1,{},[],null]){
    storage.setItem(generationPreferencesKey('a'),record({auto_review:value,use_subagents:value}));
    preferences.syncStorage(generationPreferencesKey('a'));
    assert.equal(preferences.autoReview,false);assert.equal(preferences.useSubagents,false);
  }
  storage.setItem(generationPreferencesKey('a'),record({auto_review:true,use_subagents:true}));
  preferences.syncStorage(generationPreferencesKey('a'));
  assert.equal(preferences.autoReview,true);assert.equal(preferences.useSubagents,true);
});

test('another tab observes migration and later deliberate opt-outs without reapplying defaults',()=>{
  const storage=memoryStorage(), changes=[];
  storage.setItem(generationPreferencesKey('a'),'{}');
  const first=createGenerationPreferences({storage}),second=createGenerationPreferences({storage,onChange:change=>changes.push(change)});
  first.setAccount('a');second.setAccount('a');
  first.setUseSubagents(false);first.setAutoReview(false);
  second.syncStorage(generationPreferencesKey('a'));
  assert.equal(second.useSubagents,false);assert.equal(second.autoReview,false);
  assert.deepEqual(changes[0].changed,['useSubagents','autoReview']);
  second.syncStorage(generationPreferencesKey('a'));assert.equal(changes.length,1);
});

test('settings defaults both native switches on and preserves explicit off choices',()=>{
  const on=renderSettings(false), off=renderSettings(false,'detailed',false,false,false);
  for(const id of ['use-subagents','auto-review']){
    assert.match(on,new RegExp('role="switch" id="'+id+'" checked'));
    assert.match(off,new RegExp('role="switch" id="'+id+'"\\s*>'));
    assert.equal((on.match(new RegExp('id="'+id+'"','g'))||[]).length,1);
  }
  assert.match(on,/生成或修改后自动 AI 审核/);
});

test('only strict boolean storage enables fusion; malformed data stays off',()=>{
  for(const value of ['broken','null','true','{"query_fusion":"true"}','{"query_fusion":1}']){
    const storage=memoryStorage();storage.setItem(generationPreferencesKey('a'),value);
    const preferences=createGenerationPreferences({storage});preferences.setAccount('a');
    assert.equal(preferences.queryFusion,false);
  }
});

test('unavailable storage retains a usable account-scoped session preference',()=>{
  const storage={getItem:()=>{throw Error('blocked');},setItem:()=>{throw Error('blocked');}};
  const preferences=createGenerationPreferences({storage});preferences.setAccount('a');
  preferences.setQueryFusion(true);assert.deepEqual(preferences.requestFields(),{query_fusion:true,auto_review:true});
  preferences.setAccount('a');assert.equal(preferences.queryFusion,true);
  preferences.setQueryFusion(false);assert.deepEqual(preferences.requestFields(),{auto_review:true});
  preferences.setQueryFusion(true);preferences.setAccount('b');assert.equal(preferences.queryFusion,false);
});

test('external storage changes affect only the active account and publish actual changes',()=>{
  const storage=memoryStorage(), changes=[],preferences=createGenerationPreferences({storage,onChange:c=>changes.push(c)});
  preferences.setAccount('a');
  storage.setItem(generationPreferencesKey('b'),'{"query_fusion":true}');preferences.syncStorage(generationPreferencesKey('b'));
  assert.equal(preferences.queryFusion,false);assert.deepEqual(changes,[]);
  storage.setItem(generationPreferencesKey('a'),'{"query_fusion":true}');preferences.syncStorage(generationPreferencesKey('a'));
  assert.equal(preferences.queryFusion,true);assert.equal(changes.length,1);
  preferences.syncStorage(generationPreferencesKey('a'));assert.equal(changes.length,1);
  storage.setItem(generationPreferencesKey('a'),'{}');preferences.syncStorage(null);
  assert.equal(preferences.queryFusion,false);assert.equal(changes.length,2);
});

test('a preference change invalidates a pending check while preserving the caller draft',async()=>{
  const storage=memoryStorage(),calls=[];let finish;
  const reply=new Promise(resolve=>{finish=resolve;});
  const flow=createGenerationFlow({request:async(path,method,body)=>{calls.push({path,body});return reply;}});
  const preferences=createGenerationPreferences({storage,onChange:()=>flow.cancel()});preferences.setAccount('a');
  const draft={topic:'Explain this step',course_id:'course-a',request_key:'first'};
  const original=structuredClone(draft);const pending=flow.start({...draft,...preferences.requestFields()});
  storage.setItem(generationPreferencesKey('a'),'{"query_fusion":true}');preferences.syncStorage(generationPreferencesKey('a'));
  finish({preparation_id:'a'.repeat(32),status:'ready',options:[],expires_at:1900000000});await pending;
  assert.equal(flow.state.phase,'cancelled');assert.equal(calls.length,1);assert.deepEqual(draft,original);
});

test('fusion is captured in prepare and generation retries while the original topic stays untouched',async()=>{
  const storage=memoryStorage(), preferences=createGenerationPreferences({storage}),calls=[];
  preferences.setAccount('a');preferences.setQueryFusion(true);
  const snapshot={topic:'Explain the fast thing',request_key:'one',...preferences.requestFields()};
  const flow=createGenerationFlow({request:async(path,method,body)=>{
    calls.push({path,body:structuredClone(body)});
    if(path.endsWith('/prepare'))return {preparation_id:'a'.repeat(32),status:'ready',options:[],expires_at:1900000000};
    if(calls.length===2)throw Error('network');
    return {job_id:'one'};
  }});
  await assert.rejects(flow.start(snapshot),/network/);preferences.setQueryFusion(false);await flow.retry();
  assert.equal(calls[0].body.query_fusion,true);assert.equal(calls[1].body.query_fusion,true);
  assert.deepEqual(calls[1],calls[2]);assert.equal(calls[2].body.topic,'Explain the fast thing');
});

test('per-question agent choice is frozen through preparation and retry',async()=>{
  const preferences=createGenerationPreferences({storage:memoryStorage()}), calls=[];
  preferences.setAccount('a');preferences.setUseSubagents(true);
  const snapshot={material:'assignment',topic:'Compare two algorithms',request_key:'subagent-one',
    ...preferences.requestFields('assignment')};
  const flow=createGenerationFlow({request:async(path,method,body)=>{
    calls.push({path,body:structuredClone(body)});
    if(path.endsWith('/prepare'))return {preparation_id:'a'.repeat(32),status:'ready',options:[],expires_at:1900000000};
    if(calls.length===2)throw Error('network');
    return {job_id:'one'};
  }});
  await assert.rejects(flow.start(snapshot),/network/);
  preferences.setUseSubagents(false);
  await flow.retry();
  assert.equal(calls[0].body.use_subagents,true);
  assert.equal(calls[1].body.use_subagents,true);
  assert.deepEqual(calls[1],calls[2]);
});

test('automatic review is captured in preparation, generation, and uncertain submission retries',async()=>{
  const preferences=createGenerationPreferences({storage:memoryStorage()}), calls=[];
  preferences.setAccount('a');preferences.setAutoReview(true);
  const snapshot={material:'lesson',topic:'Explain source verification',request_key:'review-one',
    ...preferences.requestFields('lesson')};
  const flow=createGenerationFlow({request:async(path,method,body)=>{
    calls.push({path,body:structuredClone(body)});
    if(path.endsWith('/prepare'))return {preparation_id:'a'.repeat(32),status:'ready',options:[],expires_at:1900000000};
    if(calls.length===2)throw Error('network');
    return {job_id:'one'};
  }});
  await assert.rejects(flow.start(snapshot),/network/);
  preferences.setAutoReview(false);
  await flow.retry();
  assert.equal(calls[0].body.auto_review,true);
  assert.equal(calls[1].body.auto_review,true);
  assert.deepEqual(calls[1],calls[2],'a retry keeps the original review preference and request identity');
  await flow.start({...snapshot,request_key:'review-two',auto_review:false},{check:false});
  assert.equal(calls.at(-1).body.auto_review,false);
});

test('minimal settings and switch preserve bilingual accessible labels and escape model names',()=>{
  try{
    document.documentElement.lang='en';
    const html=renderSettings(true);
    assert.match(html,/Generation/);assert.match(html,/Fusion mode/);assert.match(html,/Model connections/);
    assert.match(html,/role="switch" id="query-fusion" checked/);
    assert.match(renderSettings(false,'detailed',false,true),/role="switch" id="use-subagents" checked/);
    assert.match(html,/Per-question agents \(quizzes &amp; assignments\)|Per-question agents \(quizzes & assignments\)/);
    assert.doesNotMatch(html,/hint|<small|调用|\bcalls?\b/);
    assert.match(renderSwitch({id:'ask',label:'生成前追问'}),/Ask before generating/);
    const models=renderModelConnections({text:{model:'<script>private</script>',configured:true}});
    assert.match(models,/&lt;script&gt;/);assert.doesNotMatch(models,/<script>/);
    document.documentElement.lang='zh-CN';assert.match(renderSettings(false),/>融合模式</);
    assert.match(renderSettings(false),/>逐题子代理（测验与作业）</);
  }finally{document.documentElement.lang='zh-CN';}
});
