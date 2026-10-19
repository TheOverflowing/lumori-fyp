import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {createSessionClient} from '../app/static/auth.js';

const code=await readFile(new URL('../app/static/workspace-startup.js',import.meta.url),'utf8');
function boot(session,hash='#generate') {
  const nodes=new Map(['auth-gate','account-name','account-initial','account-button','.app-shell','.skip'].map(id=>[id,{hidden:id!== 'auth-gate',textContent:''}]));
  nodes.set('session-bootstrap',{textContent:typeof session==='string'?session:JSON.stringify(session)});
  const document={getElementById:id=>nodes.get(id),querySelector:id=>nodes.get(id)};
  vm.runInNewContext(code,{document,location:{hash},fetch:()=>assert.fail('Startup must not check login over the network')});
  return nodes;
}
const session={user:{id:'demo',display_name:'Classroom Demo',email:'demo@example.test'},csrf_token:'valid-page-csrf',demo_course_id:'course'};

test('authenticated reload paints the workspace before the application modules load',()=>{
  const nodes=boot(session);
  assert.equal(nodes.get('auth-gate').hidden,true);
  assert.equal(nodes.get('.app-shell').hidden,false);
  assert.equal(nodes.get('account-name').textContent,'Classroom Demo');
});

test('anonymous or invalid bootstrap never paints another account',()=>{
  for(const payload of [{user:null,csrf_token:null},'broken',{user:session.user,csrf_token:null}]) {
    const nodes=boot(payload);
    assert.equal(nodes.get('.app-shell').hidden,true);
    assert.equal(nodes.get('account-name').textContent,'');
  }
});

test('a demo link hides the previous account until its bearer has been accepted',()=>{
  const other={user:{id:'other',email:'other@example.test'},csrf_token:'other-csrf'};
  assert.equal(boot(other,'#demo?token=demo-bearer').get('.app-shell').hidden,true);
  assert.equal(boot(session,'#demo?token=demo-bearer').get('.app-shell').hidden,false);
});

test('initial identity keeps the painted shell while later account changes still reset it',()=>{
  let resets=0;
  const client=createSessionClient({onReset:()=>resets++});
  client.initialize(session);assert.equal(resets,0);
  client.initialize({user:{id:'another',email:'another@example.test'},csrf_token:'another-csrf'});
  assert.equal(resets,1);
});

test('startup HTML and the app contain no fullscreen opening-workspace prompt',async()=>{
  for(const path of ['../app/static/index.html','../app/static/app.js']) {
    const source=await readFile(new URL(path,import.meta.url),'utf8');
    assert.doesNotMatch(source,/正在打开工作空间|Opening your workspace/);
  }
});
