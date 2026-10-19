import test from 'node:test';
import assert from 'node:assert/strict';
import { classroomGenerationDraft, classroomGenerationPreferences } from '../app/static/demo-generation.js';
import { createGenerationPreferences, generationPreferencesKey } from '../app/static/generation-preferences.js';
import { ensureDifficultyDraft, difficultyValidation, generationPayload } from '../app/static/difficulty.js';
import { generationDraftData } from '../app/static/draft-forms.js';

const demo={user:{id:'classroom'},demo_course_id:'prepared-course'};

test('classroom form supplies the complete one-question English presentation request',()=>{
  const draft=ensureDifficultyDraft(classroomGenerationDraft(demo,'prepared-course'));
  assert.equal(difficultyValidation(draft),null);
  const payload=generationPayload(draft);
  assert.equal(payload.material,'quiz');assert.equal(payload.language,'en');
  assert.equal(payload.question_type,'mcq');assert.equal(payload.count,1);assert.equal(payload.difficulty,'easy');
  assert.match(payload.topic,/observations, actions, rewards, and policies in reinforcement learning/);
  assert.match(payload.learner_profile,/First-year computer science students/);
  assert.equal(draft.check_missing_details,false);
  assert.deepEqual(generationDraftData(draft).topic,draft.topic);
});

test('other accounts and courses keep their own generation form',()=>{
  for (const [session,course] of [[null,'prepared-course'],[{user:{id:'teacher'}},'prepared-course'],[demo,'another-course']])
    assert.equal(classroomGenerationDraft(session,course),null);
});

test('editable classroom presets are independent copies',()=>{
  const first=classroomGenerationDraft(demo,'prepared-course');first.topic='A new goal';first.count=5;
  const next=classroomGenerationDraft(demo,'prepared-course');
  assert.equal(next.count,1);assert.notEqual(next.topic,first.topic);
});

test('classroom presets keep the migrated defaults on without overriding later opt-outs',()=>{
  const values=new Map(),storage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
  storage.setItem(generationPreferencesKey('classroom'),'{}');
  const preferences=createGenerationPreferences({storage});preferences.setAccount('classroom');
  classroomGenerationPreferences(preferences);
  assert.deepEqual(preferences.requestFields('quiz'),{auto_review:true,use_subagents:true});
  preferences.setUseSubagents(false);preferences.setAutoReview(false);
  classroomGenerationPreferences(preferences);
  classroomGenerationPreferences(preferences);
  assert.deepEqual(preferences.requestFields('quiz'),{use_subagents:false});
  const reloaded=createGenerationPreferences({storage});reloaded.setAccount('classroom');
  classroomGenerationPreferences(reloaded);
  assert.deepEqual(reloaded.requestFields('quiz'),{use_subagents:false});
});
