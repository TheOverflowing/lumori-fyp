/* Learning Studio: independent page renderers, native controls, one API boundary. */
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const page = $('#page');
const modal = $('#modal');
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const icon = name => `<img class="icon" src="/static/icons/${name}.svg" alt="">`;
const titles = {home:'课程概览', documents:'课程资料', generate:'创作学习材料', contents:'内容与审核', jobs:'任务记录', content:'内容详情', learning:'学习材料'};
const labels = {ready:'索引就绪', parsed:'待建索引', draft:'待审核', approved:'已确认', queued:'排队中', running:'处理中', succeeded:'已完成', failed:'处理失败', insufficient_evidence:'资料依据不足', index:'资料索引', generate:'内容生成', media:'媒体生成', text:'文本模型', embedding:'嵌入模型', speech:'语音模型', image:'图像模型'};
const kinds = {lesson:'学习讲解', quiz:'测验练习', assignment:'课后作业'};
const badge = status => `<span class="badge ${esc(status)}">${esc(labels[status] || status)}</span>`;
const button = (label, action, style = '', attrs = '') => `<button class="${style}" data-action="${action}" ${attrs}>${label}</button>`;
const heading = title => `<div class="page-heading"><h1>${esc(title)}</h1></div>`;
const empty = (title, description, action = '', label = '', symbol = 'book-open') => `<div class="empty-state">${icon(symbol)}<h2>${esc(title)}</h2>${description?`<p>${esc(description)}</p>`:''}${action?button(label, action):''}</div>`;
const date = value => { const d = new Date(value); return Number.isNaN(d.valueOf()) ? '' : d.toLocaleString('zh-CN', {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}); };
const state = {course:'', courses:[], revision:0, route:{page:'home'}, drafts:new Map(), content:null, learningId:new URLSearchParams(location.search).get('learn')};

async function api(path, method = 'GET', data) {
  const options = {method};
  if (data instanceof FormData) options.body = data;
  else if (data !== undefined) { options.headers = {'Content-Type':'application/json'}; options.body = JSON.stringify(data); }
  const response = await fetch('/api' + path, options);
  if (!response.ok) {
    let result; try { result = await response.json(); } catch { result = {}; }
    throw new Error(typeof result.detail === 'string' ? result.detail : `请求未完成（${response.status}），请检查输入后重试。`);
  }
  return response.json();
}
function notify(message) {
  $('#notice-text').textContent = message;
  $('#notice').hidden = false;
}
function inlineError(form, message) {
  let error = $('.error-message', form);
  if (!error) { error = document.createElement('div'); error.className = 'error-message'; error.setAttribute('role','alert'); form.prepend(error); }
  error.textContent = message;
  error.scrollIntoView({block:'nearest'});
}
async function busy(control, task, form = null) {
  if (control?.disabled) return;
  const old = control?.innerHTML;
  if (control) { control.disabled = true; control.setAttribute('aria-busy','true'); if (form) control.textContent = '正在处理…'; }
  if (form) $('.error-message', form)?.remove();
  try { await task(); }
  catch (error) { if (form?.isConnected) inlineError(form, error.message); else notify(error.message); }
  finally { if (control?.isConnected) { control.disabled = false; control.removeAttribute('aria-busy'); control.innerHTML = old; } }
}
function dialog(title, html, wide = false) {
  modal.classList.toggle('wide', wide);
  $('#modal-content').innerHTML = `<div class="dialog-top"><h2 id="modal-title">${esc(title)}</h2>${button(icon('plus'),'close-modal','plain icon-button close-button','aria-label="关闭" title="关闭"')}</div>${html}`;
  if (!modal.open) modal.showModal();
}
function courseRequired() {
  return {html:empty('暂无课程','','new-course','新建课程','files')};
}
function go(name, id = '') {
  const hash = '#' + name + (id ? '/' + encodeURIComponent(id) : '');
  if (location.hash === hash) return renderRoute();
  location.hash = hash;
}
async function loadCourses() {
  state.courses = await api('/courses');
  if (!state.courses.some(course => course.id === state.course)) state.course = state.courses[0]?.id || '';
  $('#course-select').innerHTML = state.courses.length ? state.courses.map(course => `<option value="${esc(course.id)}">${esc(course.name)}</option>`).join('') : '<option value="">选择或新建课程</option>';
  $('#course-select').value = state.course;
}
function courseUrl(resource, course = state.course) { return `/${resource}?course_id=${encodeURIComponent(course)}`; }
function renderNavigation(name) {
  const active = name === 'content' ? 'contents' : name;
  $$('nav a').forEach(link => { if (link.dataset.page === active) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current'); });
  $('#route-label').textContent = titles[name] || titles.home;
  document.title = `${titles[name] || titles.home} · 知序`;
}
async function renderRoute() {
  const revision = ++state.revision;
  const [requested = 'home', rawId = ''] = location.hash.slice(1).split('/');
  const name = state.learningId ? 'learning' : (renderers[requested] ? requested : 'home');
  let id; try { id = decodeURIComponent(rawId); } catch { id = ''; }
  state.route = {page:name, id};
  renderNavigation(name);
  $('#toolbar-actions').innerHTML = '';
  page.innerHTML = '<div class="loading" role="status">正在载入…</div>';
  window.scrollTo({top:0,behavior:'instant'});
  try {
    const result = await renderers[name](id);
    if (revision !== state.revision) return;
    page.innerHTML = result.html;
    $('#toolbar-actions').innerHTML = result.toolbar || '';
    result.bind?.();
  } catch (error) {
    if (revision !== state.revision) return;
    page.innerHTML = empty('暂时无法载入', error.message, 'retry', '重新尝试');
  }
}
function materialRow(content) {
  return `<div class="collection-row"><span class="file-icon">${icon('book-open')}</span><div class="row-main"><h3>${esc(content.title)}</h3><p>版本 ${content.version} · ${esc(date(content.created_at))}</p></div>${badge(content.status)}<div class="row-actions">${button('打开','open-content','secondary',`data-id="${esc(content.id)}"`)}</div></div>`;
}

async function renderHome() {
  if (!state.course) return {...courseRequired(), toolbar:button('模型连接','settings','secondary')};
  const course = state.courses.find(item => item.id === state.course);
  const [docs, contents] = await Promise.all([api(courseUrl('documents')), api(courseUrl('contents'))]);
  const drafts = contents.filter(content => content.status === 'draft').length;
  return {
    toolbar:button(icon('upload')+'导入资料','upload','secondary'),
    html:`<section class="overview-heading"><h1>${esc(course.name)}</h1><div class="course-stats"><div><strong>${docs.length}</strong><span>资料</span></div><div><strong>${contents.length}</strong><span>材料</span></div><div><strong>${drafts}</strong><span>待审核</span></div></div></section>
      <div class="home-grid"><section class="creation-section" aria-label="创作材料"><div class="quick-create">${[['lesson','book-open'],['quiz','layers'],['assignment','file-text']].map(([kind,symbol])=>button(`${icon(symbol)}<strong>${kinds[kind]}</strong><img class="choice-arrow" src="/static/icons/arrow-up-right.svg" alt="">`,'create-kind','create-choice',`data-kind="${kind}"`)).join('')}</div></section>
      <section class="home-panel materials-panel"><div class="heading-row"><h2>最近材料</h2>${button(icon('arrow-right'),'contents','plain icon-button','aria-label="查看全部材料" title="查看全部材料"')}</div>${contents.length?`<div class="collection">${contents.slice(0,4).map(materialRow).join('')}</div>`:`<div class="recent-empty">${icon('book-open')}<p>暂无材料</p></div>`}</section>
      <section class="home-panel documents-panel"><div class="heading-row"><h2>课程资料</h2>${button(icon('arrow-right'),'documents','plain icon-button','aria-label="管理课程资料" title="管理课程资料"')}</div>${docs.length?`<div class="collection">${docs.slice(0,3).map(doc=>`<div class="collection-row"><span class="file-icon">${icon('file-text')}</span><div class="row-main"><h3>${esc(doc.name)}</h3><p>${doc.pages} 页</p></div>${badge(doc.index_current?'ready':'parsed')}</div>`).join('')}</div>`:'<div class="recent-empty"><p>暂无资料</p></div>'}</section></div>`
  };
}

async function renderDocuments() {
  if (!state.course) return courseRequired();
  const docs = await api(courseUrl('documents'));
  return {
    toolbar:button(icon('upload')+'导入资料','upload'),
    html:heading('课程资料')+`<div class="collection-tools"><div class="segmented" aria-label="资料状态筛选"><button data-filter="all" aria-pressed="true">全部 ${docs.length}</button><button data-filter="ready" aria-pressed="false">索引就绪</button><button data-filter="parsed" aria-pressed="false">待建索引</button></div><label class="search"><span class="sr-only">搜索文件</span><input id="file-search" type="search" placeholder="搜索文件名称"></label></div><div id="files"></div>`,
    bind() {
      let filter = 'all';
      const paint = () => {
        const query = $('#file-search').value.trim().toLowerCase();
        const rows = docs.filter(doc => doc.name.toLowerCase().includes(query) && (filter==='all'||(filter==='ready')===Boolean(doc.index_current)));
        $('#files').innerHTML = rows.length ? `<div class="collection">${rows.map(doc=>`<div class="collection-row"><span class="file-icon">${icon('file-text')}</span><div class="row-main"><h3>${esc(doc.name)}</h3><p>${doc.pages} 页 · ${doc.chunks} 个知识片段</p></div>${badge(doc.index_current?'ready':'parsed')}<div class="row-actions">${button('阅读片段','chunks','secondary',`data-id="${esc(doc.id)}" data-name="${esc(doc.name)}"`)}${button(doc.index_current?'重建索引':'建立索引','index','secondary',`data-id="${esc(doc.id)}"`)}</div></div>`).join('')}</div>` : empty(docs.length?'没有匹配的资料':'暂无资料',docs.length?'试试其他名称或筛选条件。':'',docs.length?'':'upload','导入资料','files');
      };
      $('#file-search').oninput = paint;
      $$('[data-filter]').forEach(control => control.onclick = () => {filter=control.dataset.filter;$$('[data-filter]').forEach(item=>item.setAttribute('aria-pressed',String(item===control)));paint();});
      paint();
    }
  };
}
function draftFor(course = state.course) {
  if (!state.drafts.has(course)) state.drafts.set(course,{material:'lesson',topic:'',difficulty:'medium',language:'zh',question_type:'mixed',count:3});
  return state.drafts.get(course);
}
async function renderGenerate() {
  if (!state.course) return courseRequired();
  const course = state.course;
  const draft = draftFor(course);
  const [docs,status] = await Promise.all([api(courseUrl('documents',course)),api('/status')]);
  const ready = docs.filter(doc=>doc.index_current).length;
  const select = (id,label,values) => `<label>${label}<select id="${id}" name="${id}">${values.map(([value,text])=>`<option value="${value}" ${String(draft[id])===value?'selected':''}>${text}</option>`).join('')}</select></label>`;
  return {
    toolbar:button('模型连接','settings','secondary'),
    html:heading('创作学习材料')+`<div class="compose-layout"><form id="compose" class="compose-form"><fieldset><legend class="sr-only">材料类型</legend><div class="type-switch">${Object.entries(kinds).map(([kind,title])=>`<label><input type="radio" name="material" value="${kind}" ${draft.material===kind?'checked':''}>${title}</label>`).join('')}</div></fieldset>
      <div class="writing-field"><label for="topic">学习目标</label><textarea id="topic" name="topic" required minlength="2" maxlength="300" placeholder="输入知识点或学习目标">${esc(draft.topic)}</textarea><div class="field-meta"><span id="character-count"></span></div></div>
      <div class="field-grid">${select('difficulty','目标难度',[['easy','基础 · 理解概念'],['medium','应用 · 迁移运用'],['hard','综合 · 分析整合']])}${select('language','内容语言',[['zh','中文'],['en','English']])}</div><div class="field-grid" id="question-options">${select('question_type','题目形式',[['mixed','选择题与简答题'],['mcq','选择题'],['short_answer','简答题']])}<label>题目数量<input type="number" name="count" id="count" min="1" max="10" required value="${draft.count}"></label></div>
      <div class="submit-bar"><button type="submit">${icon('wand-sparkles')}开始生成</button></div></form>
      <aside class="context-pane"><div class="context-title">本次创作</div><h2 id="draft-kind"></h2><p id="draft-summary"></p><div class="context-divider"></div><div class="heading-row"><h3>课程知识</h3><small>${ready} / ${docs.length} 份就绪</small></div>${docs.slice(0,4).map(doc=>`<div class="context-file">${icon('file-text')}<span>${esc(doc.name)}</span></div>`).join('')||'<p>尚未导入课程资料。</p>'}${button('管理课程资料','documents','link')}<div class="inline-note">${ready?'索引就绪':'请先建立索引'}</div>${!status.capabilities.text.configured||!status.capabilities.embedding.configured?button('配置文本与嵌入模型','settings','link'):''}<details><summary>关于内容与引用</summary><p>模型依据检索片段生成内容，系统检查格式与引用标识。事实是否正确、引用是否支持结论，仍需要你对照原文判断。</p></details></aside></div>`,
    bind() {
      const form=$('#compose');
      const update=()=>{
        const data=new FormData(form);
        for (const key of ['topic','material','difficulty','language','question_type']) if(data.has(key)) draft[key]=data.get(key);
        if(data.has('count')) draft.count=Number(data.get('count'));
        const lesson=draft.material==='lesson';
        $('#question-options').hidden=lesson;$('#count').disabled=lesson;$('#question_type').disabled=lesson;
        $('#character-count').textContent=`${draft.topic.length} / 300`;
        $('#draft-kind').textContent=kinds[draft.material];
        $('#draft-summary').textContent=`${draft.language==='zh'?'中文':'English'} · ${{easy:'基础',medium:'应用',hard:'综合'}[draft.difficulty]}${lesson?'':` · ${draft.count||'—'} 道题`}`;
      };
      form.oninput=update;form.onchange=update;update();
      form.onsubmit=event=>{event.preventDefault();busy($('button[type=submit]',form),async()=>{update();await api('/generations','POST',{...draft,count:draft.material==='lesson'?3:draft.count,course_id:course,request_key:crypto.randomUUID()});notify('生成任务已创建，可在任务记录中查看进度。');go('jobs');},form);};
    }
  };
}
async function renderContents() {
  if (!state.course) return courseRequired();
  const rows=await api(courseUrl('contents'));
  return {
    toolbar:button(icon('plus')+'创作材料','generate'),
    html:heading('内容与审核')+`<div class="collection-tools"><div class="segmented" aria-label="内容状态筛选"><button data-content-filter="all" aria-pressed="true">全部</button><button data-content-filter="draft" aria-pressed="false">待审核 ${rows.filter(c=>c.status==='draft').length}</button><button data-content-filter="approved" aria-pressed="false">已确认</button></div><label class="search"><span class="sr-only">搜索学习材料</span><input id="content-search" type="search" placeholder="搜索材料标题"></label></div><div id="content-list"></div>`,
    bind(){let filter='all';const paint=()=>{const q=$('#content-search').value.trim().toLowerCase();const selected=rows.filter(c=>(filter==='all'||c.status===filter)&&c.title.toLowerCase().includes(q));$('#content-list').innerHTML=selected.length?`<div class="collection">${selected.map(materialRow).join('')}</div>`:empty(rows.length?'没有匹配的内容':'暂无材料',rows.length?'调整筛选条件或搜索名称。':'','generate','开始创作');};$('#content-search').oninput=paint;$$('[data-content-filter]').forEach(control=>control.onclick=()=>{filter=control.dataset.contentFilter;$$('[data-content-filter]').forEach(item=>item.setAttribute('aria-pressed',String(item===control)));paint();});paint();}
  };
}
function renderAsset(asset, showCitations=true) {
  const cites=ids=>showCitations?`<div class="citations">资料片段 · ${ids.map(esc).join(' · ')}</div>`:'';
  return `<h2>${esc(asset.title)}</h2>${asset.learning_objectives?.length?`<p class="objective">学习目标：${asset.learning_objectives.map(esc).join('；')}</p>`:''}${asset.sections.map(section=>`<h3>${esc(section.heading)}</h3><div class="prose">${esc(section.text)}</div>${cites(section.citation_ids)}`).join('')}${asset.questions.map((question,index)=>`<section class="question"><h3>${index+1}. ${esc(question.stem)}</h3>${question.options.length?`<ol type="A">${question.options.map(option=>`<li>${esc(option)}</li>`).join('')}</ol>`:''}${cites(question.citation_ids)}${question.answer!==undefined?`<details><summary>参考答案与解析</summary><div class="answer"><p><strong>${esc(question.answer)}</strong></p><p>${esc(question.explanation)}</p><p>难度设计：${esc(question.difficulty_reason||'')}</p></div></details>`:''}</section>`).join('')}`;
}
function renderMedia(media, review=false, version=0) {
  return media.map(item=>`<div class="media-item"><div class="row-actions"><small>${item.kind==='audio'?'AI 合成语音':'AI 生成配图'}</small>${review?badge(item.status):''}</div>${item.kind==='audio'?`<audio controls preload="metadata" src="/api/media/${encodeURIComponent(item.id)}/file"></audio>${item.metadata?.transcript?`<p>${esc(item.metadata.transcript)}</p>`:''}`:`<img loading="lazy" src="/api/media/${encodeURIComponent(item.id)}/file" alt="${review?'待核对的':'已审核的'}教学辅助配图">`}${review?button(item.status==='approved'?'媒体已确认':'确认媒体内容','approve-media','secondary',`data-id="${esc(item.id)}" data-version="${version}" ${item.status==='approved'?'disabled':''}`):''}</div>`).join('');
}
async function renderContent(id) {
  const content=await api('/contents/'+encodeURIComponent(id));
  const cid=encodeURIComponent(id);
  return {
    toolbar:button('返回内容库','contents','secondary'),
    html:`<div class="review-bar">${badge(content.status)}<small>版本 ${content.version}</small><a href="/api/contents/${cid}/export">导出 Markdown</a><a href="/api/contents/${cid}/evidence">导出生成依据</a>${content.status==='approved'?`<a href="/?learn=${cid}" target="_blank" rel="noopener">打开学习页</a>`:''}</div><div class="review-layout"><div><article class="document-paper">${renderAsset(content.asset)}<div class="submit-bar"><div class="row-actions">${button('编辑内容','edit-content','secondary')}${button(content.status==='approved'?'文字已确认':'确认文字','approve-content','',content.status==='approved'?'disabled':'')}</div></div><div id="edit-panel"></div></article></div>
      <aside class="review-inspector"><section class="inspector-section"><h2>资料依据</h2>${content.sources.map((source,index)=>`<details ${index===0?'open':''}><summary>${esc(source.document_name)} · 第 ${source.page} 页</summary><div class="source-chunk"><p>${esc(source.text)}</p><small>${esc(source.id)}</small></div></details>`).join('')}</section>
      <section class="inspector-section"><h2>更多表达方式</h2><p>确认文字后可生成</p><div class="row-actions">${button(icon('audio-lines')+'生成语音','make-media','secondary',`data-kind="audio" ${content.status!=='approved'?'disabled':''}`)}${button(icon('image')+'生成配图','make-media','secondary',`data-kind="image" ${content.status!=='approved'?'disabled':''}`)}</div>${renderMedia(content.media,true,content.version)}</section>
      <section class="inspector-section"><h2>评价当前版本</h2><p>1 分最低，5 分最高。</p><form id="evaluation">${[['correctness','内容正确性'],['groundedness','资料支持度'],['difficulty_match','难度匹配度']].map(([name,label])=>`<label>${label}<select name="${name}" required><option value="">选择评分</option>${[1,2,3,4,5].map(n=>`<option value="${n}">${n} 分</option>`).join('')}</select></label>`).join('')}<label>观察记录<textarea name="notes" maxlength="2000" placeholder="记录值得保留或需要改进的地方"></textarea></label><button type="submit" class="secondary">保存评价</button></form><p><a class="link" href="/api/evaluations/export">导出评价 CSV</a></p></section></aside></div>`,
    bind(){state.content=content;$('#evaluation').onsubmit=event=>{event.preventDefault();const form=event.currentTarget;busy($('button[type=submit]',form),async()=>{const fields=new FormData(form);await api(`/contents/${cid}/evaluations`,'POST',{version:content.version,notes:fields.get('notes'),...Object.fromEntries(['correctness','groundedness','difficulty_match'].map(key=>[key,Number(fields.get(key))]))});notify('当前版本的评价已保存。');},form);};}
  };
}
function editContent() {
  const content=state.content;
  const asset=structuredClone(content.asset);
  const field=(title,path,value,max=6000)=>`<label>${esc(title)}<textarea data-path="${path}" required maxlength="${max}">${esc(value)}</textarea></label>`;
  $('#edit-panel').innerHTML=`<div class="edit-panel"><h3>编辑版本 ${content.version}</h3><p>保存为新版本后，需要重新确认。引用标识将保留，请确保修改后仍有资料支持。</p><form id="edit-form">${field('标题','title',asset.title,200)}${asset.sections.map((section,index)=>field(`小节 ${index+1} 标题`,`sections.${index}.heading`,section.heading,200)+field(`小节 ${index+1} 内容`,`sections.${index}.text`,section.text)).join('')}${asset.questions.map((question,index)=>field(`第 ${index+1} 题`,`questions.${index}.stem`,question.stem,3000)+question.options.map((option,i)=>field(`选项 ${String.fromCharCode(65+i)}`,`questions.${index}.options.${i}`,option,3000)).join('')+field('参考答案',`questions.${index}.answer`,question.answer,3000)+field('答案解析',`questions.${index}.explanation`,question.explanation,4000)).join('')}<label>配图描述<textarea data-path="visual_prompt" maxlength="3000">${esc(asset.visual_prompt)}</textarea></label><div class="modal-actions">${button('取消编辑','cancel-edit','secondary','type="button"')}<button type="submit">保存新版本</button></div></form></div>`;
  $('#edit-panel').scrollIntoView({block:'start',behavior:'instant'});
  $('#edit-form').onsubmit=event=>{event.preventDefault();const form=event.currentTarget;busy($('button[type=submit]',form),async()=>{$$('[data-path]',form).forEach(input=>{const keys=input.dataset.path.split('.');let target=asset;for(const key of keys.slice(0,-1))target=target[key];target[keys.at(-1)]=input.value;});await api(`/contents/${encodeURIComponent(content.id)}/review`,'POST',{version:content.version,action:'save',asset});notify('新版本已保存，请重新审核。');await renderRoute();},form);};
}
async function renderJobs() {
  const rows=await api('/jobs');
  return {
    toolbar:button('刷新状态','retry','secondary'),
    html:heading('任务记录')+(rows.length?`<div class="collection">${rows.map(job=>`<div class="collection-row"><span class="file-icon">${icon('clock-3')}</span><div class="row-main"><h3>${esc(labels[job.kind]||job.kind)}</h3><p>${esc(date(job.created_at))}${job.error?' · '+esc(job.error):''}</p></div>${badge(job.status)}<div class="row-actions">${button('查看详情','job-details','secondary',`data-id="${esc(job.id)}"`)}</div></div>`).join('')}</div>`:empty('暂无任务','','documents','前往课程资料','clock-3'))
  };
}
async function renderLearning() {
  document.body.classList.add('learning');
  const data=await api(`/learn/${encodeURIComponent(state.learningId)}?reveal_answers=${Boolean(state.reveal)}`);
  return {html:`<article class="document-paper">${renderAsset(data.asset,false)}${!state.reveal&&data.asset.questions.length?`<div class="submit-bar">${button('查看答案与解析','reveal')}</div>`:''}${renderMedia(data.media)}</article>`};
}
const renderers={home:renderHome,documents:renderDocuments,generate:renderGenerate,contents:renderContents,jobs:renderJobs,content:renderContent,learning:renderLearning};

const actions={
  home:()=>go('home'), documents:()=>go('documents'), generate:()=>go('generate'), contents:()=>go('contents'), retry:renderRoute,
  'close-modal':()=>modal.close(),
  'new-course':()=>{
    dialog('新建课程','<form id="new-course-form"><label>课程名称<input name="name" required maxlength="120" placeholder="例如：机器学习基础" autocomplete="off"></label><div class="modal-actions">'+button('取消','close-modal','secondary','type="button"')+'<button type="submit">创建课程</button></div></form>');
    $('#new-course-form').onsubmit=event=>{event.preventDefault();const form=event.currentTarget;busy($('button[type=submit]',form),async()=>{const course=await api('/courses','POST',{name:new FormData(form).get('name')});state.course=course.id;await loadCourses();modal.close();notify('课程已创建，可以导入资料了。');go('documents');},form);};
  },
  upload:()=>{
    if(!state.course) return actions['new-course']();
    const course=state.course;
    dialog('导入课程资料','<p>支持文本型 PDF、TXT 和 Markdown，单份最大 10 MB、300 页。</p><form id="upload-form"><label>选择文件<input type="file" name="file" accept=".pdf,.txt,.md" required></label><p>扫描件需要先转换成可提取文字的文件。</p><div class="modal-actions">'+button('取消','close-modal','secondary','type="button"')+'<button type="submit">导入并解析</button></div></form>');
    $('#upload-form').onsubmit=event=>{event.preventDefault();const form=event.currentTarget;busy($('button[type=submit]',form),async()=>{const data=new FormData(form);data.append('course_id',course);const result=await api('/documents','POST',data);modal.close();notify(result.duplicate?'这份资料已经导入。':'资料已解析，可以查看片段并建立索引。');go('documents');},form);};
  },
  settings:async()=>{
    const status=await api('/status');
    dialog('模型连接',`<p>按需连接不同能力。填写配置后，需要实际调用验证连接。</p>${Object.entries(status.capabilities).map(([key,cap])=>`<div class="connection-row"><div class="row-main"><h3>${labels[key]}</h3><p>${esc(cap.model||'尚未指定模型')}</p></div><span class="badge ${cap.configured?'ready':''}">${cap.configured?'已填写配置':'未配置'}</span></div>`).join('')}<div class="inline-note">在本地 .env 文件中设置服务地址、模型名称和密钥，然后重启应用。密钥不会显示在网页中。</div><p class="muted">今日调用 ${status.calls_today} / ${status.daily_call_limit} · UTC</p>`);
  },
  'create-kind':control=>{draftFor().material=control.dataset.kind;go('generate');},
  'open-content':control=>go('content',control.dataset.id),
  chunks:async control=>{const rows=await api(`/documents/${encodeURIComponent(control.dataset.id)}/chunks`);dialog(control.dataset.name,rows.map(chunk=>`<section class="source-chunk"><h3>第 ${chunk.page} 页</h3><p>${esc(chunk.text)}</p></section>`).join(''),true);},
  index:async control=>{await api(`/documents/${encodeURIComponent(control.dataset.id)}/index`,'POST');notify('索引任务已创建。');go('jobs');},
  'job-details':async control=>{const job=await api(`/jobs/${encodeURIComponent(control.dataset.id)}`);if(job.result?.content_id)return go('content',job.result.content_id);dialog('任务详情',`${badge(job.status)}<div class="inline-note">${esc(job.error||job.result?.message||(job.status==='succeeded'?'处理完成，可以返回资料库查看索引状态。':'任务正在处理，请稍后刷新状态。'))}</div>`);},
  'approve-content':async()=>{const content=state.content;await api(`/contents/${encodeURIComponent(content.id)}/review`,'POST',{version:content.version,action:'approve'});notify('文字已确认，可以打开学习页或制作媒体。');await renderRoute();},
  'edit-content':editContent,
  'cancel-edit':()=>{$('#edit-panel').innerHTML='';},
  'make-media':async control=>{const content=state.content;await api(`/contents/${encodeURIComponent(content.id)}/media`,'POST',{version:content.version,kind:control.dataset.kind,request_key:crypto.randomUUID()});notify('媒体生成任务已创建。');go('jobs');},
  'approve-media':async control=>{await api(`/media/${encodeURIComponent(control.dataset.id)}/approve`,'POST',{version:Number(control.dataset.version)});notify('媒体内容已确认。');await renderRoute();},
  reveal:async()=>{state.reveal=true;await renderRoute();}
};

document.addEventListener('click',event=>{const control=event.target.closest('[data-action]');if(!control)return;const action=actions[control.dataset.action];if(action){event.preventDefault();busy(control,()=>action(control));}});
document.addEventListener('pointerdown',()=>document.body.dataset.input='pointer',{capture:true,passive:true});
document.addEventListener('keydown',()=>document.body.dataset.input='keyboard',{capture:true});
$('.skip').onclick=event=>{event.preventDefault();$('#main').focus();$('#main').scrollIntoView({block:'start',behavior:'instant'});};
$('#notice .notice-close').onclick=()=>$('#notice').hidden=true;
$('#course-select').onchange=async()=>{state.course=$('#course-select').value;state.content=null;if(state.route.page==='content')go('contents');else await renderRoute();};
window.addEventListener('hashchange',renderRoute);
(async()=>{try{if(!state.learningId)await loadCourses();await renderRoute();}catch(error){page.innerHTML=empty('无法连接工作空间',error.message,'retry','重试');}})();
