import test from 'node:test';
import assert from 'node:assert/strict';
import { courseOverview, renderStudioIntro } from '../app/static/studio-home.js';

globalThis.document = {documentElement:{lang:'zh-CN'}};

test('new courses point to an import and do not imply that materials were reviewed', () => {
  const summary = courseOverview([], []);
  assert.equal(summary.action, 'upload');
  const html = renderStudioIntro({course:{name:'New course'},documents:[],contents:[]});
  assert.match(html,/等待第一份材料/);
  assert.doesNotMatch(html,/所有材料已确认/);
});

test('only current enabled sources count as usable; deleted sources do not choose a preparation path', () => {
  assert.equal(courseOverview([{deleted_at:'today',index_current:true}]).action,'upload');
  const summary = courseOverview([{index_current:false},{index_current:true,enabled:false}]);
  assert.equal(summary.ready,0);
  assert.equal(summary.action,'documents');
  assert.equal(courseOverview([{index_current:true}]).action,'generate');
});

test('review counts are actual drafts and authored course names remain escaped and untranslated', () => {
  document.documentElement.lang='en';
  try {
    const html = renderStudioIntro({course:{name:'课程 <script>alert(1)</script>'},documents:[{index_current:true}],contents:[{status:'draft'},{status:'approved'}]});
    assert.match(html,/1 awaiting review/);
    assert.match(html,/2 materials created/);
    assert.match(html,/课程 &lt;script&gt;/);
    assert.doesNotMatch(html,/<script>/);
  } finally { document.documentElement.lang='zh-CN'; }
});
