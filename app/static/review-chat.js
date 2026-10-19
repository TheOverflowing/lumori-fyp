import { a, m, setText, t } from './i18n.js';
import { renderReadableText } from './readable-text.js';
import { questionSlot } from './question-revision.js';
import { createRequestId } from './request-id.js';
import { watchResource } from './live-updates.js';

const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const fieldLabels = {stem:'题干',options:'选项',answer:'参考答案',explanation:'答案解析',difficulty:'目标难度',citation_ids:'引用来源'};
const difficultyLabels = {easy:'简单',medium:'中等',hard:'困难'};
const actions = {rewrite:'已改写题目',explanation:'已修改解析',undo:'已撤销修改'};
const choiceOptions = content => `<option value="" data-i18n="整份材料">${escape(t('整份材料'))}</option>${(content.asset?.questions || []).map((question,index)=>`<option value="${escape(questionSlot(question,index))}" data-i18n="第 {n} 题" data-i18n-values="${escape(JSON.stringify({n:index+1}))}">${escape(t('第 {n} 题',{n:index+1}))}</option>`).join('')}`;
const changeValue = (value,field) => field === 'difficulty' && Object.hasOwn(difficultyLabels,value) ? m(difficultyLabels[value]) : Array.isArray(value) ? `<ol type="A">${value.map(item=>`<li>${renderReadableText(item,escape)}</li>`).join('')}</ol>` : renderReadableText(value == null ? '—' : typeof value === 'object' ? JSON.stringify(value) : value,escape);

export function renderReviewChatMessages(messages, {version,busy=false,editing=false} = {}) {
  const undoId = [...messages].reverse().find(message => message.can_undo && message.version === version)?.id;
  if (!messages.length) return `<div class="review-chat-empty"><img src="/static/icons/wand-sparkles.svg" alt=""><p>${m('一起完善这份材料')}</p><span>${m('选中一道题，告诉我想怎么改；也可以直接提问。')}</span></div>`;
  return messages.map(message => {
    const role = message.role === 'user' ? 'user' : 'assistant';
    const changes = Array.isArray(message.changes) ? message.changes : [];
    const action = Object.hasOwn(actions,message.action) ? actions[message.action] : null;
    return `<article class="review-chat-message" data-role="${role}" data-chat-message="${escape(message.id)}"><header><span>${m(role === 'user' ? '你' : '修改助手')}</span>${action ? `<small>${m(action)}</small>` : ''}</header><div class="readable-text">${message.action === 'undo' ? `<p>${m('已撤销上一次修改。')}</p>` : renderReadableText(message.text,escape)}</div>${changes.length ? `<details class="review-chat-comparison" data-chat-comparison="${escape(message.id)}"><summary>${m('查看修改前后')}</summary>${changes.map(change=>`<section><h4>${m(Object.hasOwn(fieldLabels,change.field) ? fieldLabels[change.field] : change.label || change.field || '修改内容')}</h4><div class="review-chat-change" data-side="before"><span>${m('修改前')}</span><div class="readable-text">${changeValue(change.before,change.field)}</div></div><div class="review-chat-change" data-side="after"><span>${m('修改后')}</span><div class="readable-text">${changeValue(change.after,change.field)}</div></div></section>`).join('')}</details>` : ''}${message.id === undoId ? `<button type="button" class="link review-chat-undo" data-chat-undo="${escape(message.id)}" ${busy || editing ? 'disabled' : ''}>${m('撤销这次修改')}</button>` : ''}</article>`;
  }).join('');
}

export function renderReviewChat(content = {}) {
  return `<section class="review-chat" data-review-chat ${a('与修改助手对话','aria-label')}><details class="review-chat-disclosure" data-chat-disclosure open><summary><span class="review-chat-heading"><img src="/static/icons/wand-sparkles.svg" alt="">${m('修改助手')}</span><span class="review-chat-toggle" aria-hidden="true"></span></summary><div class="review-chat-body"><div class="review-chat-context"><label for="review-chat-question">${m('当前讨论')}</label><select id="review-chat-question" data-chat-question>${choiceOptions(content)}</select></div><div class="review-chat-log" data-chat-log role="log" aria-live="polite" aria-relevant="additions text" ${a('对话记录','aria-label')} tabindex="0">${renderReviewChatMessages([])}</div><p class="review-chat-status" data-chat-status role="status" aria-live="polite"></p><div class="review-chat-error" data-chat-error hidden><p data-chat-error-text role="alert"></p><button type="button" class="link" data-chat-reload>${m('重新连接')}</button></div><form class="review-chat-form" data-chat-form><label class="sr-only" for="review-chat-message">${m('提问或描述修改要求')}</label><textarea id="review-chat-message" data-chat-input rows="3" maxlength="2000" required ${a('例如：把这道题换成生活中的例子','placeholder')}></textarea><div class="review-chat-compose-footer"><span>${m('Shift + Enter 换行')}</span><button type="submit" data-chat-send disabled>${m('发送')}</button></div></form></div></details></section>`;
}

export function bindReviewChat(root, initial, {load,send,undo,onContentUpdated=async()=>{},isEditing=()=>false,getAutoReview=()=>false,isActive=()=>true,interval=2500,visibility=document,makeKey=()=>createRequestId()} = {}) {
  const panel = root.matches?.('[data-review-chat]') ? root : root.querySelector('[data-review-chat]');
  if (!panel) return Object.assign(()=>{}, {updateContent(){},refresh(){},selectQuestion(){},isBusy:()=>false});
  const find = selector => panel.querySelector(selector);
  const log=find('[data-chat-log]'), input=find('[data-chat-input]'), question=find('[data-chat-question]'), form=find('[data-chat-form]'), submit=find('[data-chat-send]'), status=find('[data-chat-status]'), errorBox=find('[data-chat-error]'), errorText=find('[data-chat-error-text]'), reload=find('[data-chat-reload]'), disclosure=find('[data-chat-disclosure]');
  let content=initial, snapshot={version:initial.version,messages:[],active_job_id:null};
  let disposed=false, loading=true, pending='', updating=false, controller, reading, stop, error='', errorKind='', reloadNeeded=false, fingerprint='', requestKey, undoFingerprint='', undoKey, rendered='';
  const active = () => !disposed && panel.isConnected !== false && isActive();
  const busy = () => loading || Boolean(pending || snapshot.active_job_id || updating);
  const mismatched = () => snapshot.version !== content.version;
  const stopPolling = () => { stop?.();stop=undefined; };
  const paint = () => {
    if (!active()) return;
    const editing=isEditing();
    const next=renderReviewChatMessages(snapshot.messages,{version:content.version,busy:busy() || mismatched(),editing});
    if (next !== rendered) {
      const nearEnd=log.scrollHeight-log.scrollTop-log.clientHeight < 64;
      const expanded=new Set([...log.querySelectorAll('[data-chat-comparison]')].filter(node=>node.open).map(node=>node.dataset.chatComparison));
      log.innerHTML=next;rendered=next;
      for (const node of log.querySelectorAll('[data-chat-comparison]')) node.open=expanded.has(node.dataset.chatComparison);
      if (nearEnd) log.scrollTop=log.scrollHeight;
    }
    const label = loading ? '正在载入对话…' : pending === 'undo' ? '正在撤销…' : pending === 'send' ? '正在发送…' : updating ? '正在更新材料…' : editing ? '请先保存或丢弃编辑草稿。' : snapshot.active_job_id ? '助手正在处理，可以继续写下一条消息。' : mismatched() ? '材料已有新版本，请重新连接。' : '可提问、改写单题或修改解析';
    if (status.dataset.i18n !== label) setText(status,label);
    errorBox.hidden=!error;
    if (error) setText(errorText,error);
    reload.hidden=!reloadNeeded;
    reload.disabled=loading || Boolean(pending) || updating;
    submit.disabled=busy() || editing || mismatched() || reloadNeeded || !input.value.trim();
    setText(submit,error && !reloadNeeded && errorKind === 'send' ? '重试发送' : '发送');
    form.setAttribute('aria-busy',pending === 'send' ? 'true' : 'false');
    panel.dataset.busy=busy() ? 'true' : 'false';
  };
  const fail = (cause, reconnect=false) => {
    if (!active() || ['AbortError','SessionChangedError'].includes(cause?.name)) return;
    errorKind=pending;
    error=cause?.uiMessage || ([400,409,422].includes(cause?.status) && cause?.message ? cause.message : reconnect ? '暂时无法载入对话，请重新连接。' : pending === 'undo' ? '撤销未完成，请重试。' : '发送未完成，请重试。');
    reloadNeeded=reconnect || cause?.status === 409;paint();
  };
  const syncContent = async () => {
    if (!active() || updating || !mismatched() || isEditing()) return;
    updating=true;paint();
    try {
      const next=await onContentUpdated(snapshot);
      if (!active()) return;
      if (next) content=next;
      if (mismatched()) throw new Error('Content refresh incomplete');
    } catch(cause) { fail(cause,true); }
    finally { if(active()){updating=false;paint();} }
  };
  const accept = async next => {
    if (!active() || !next || Number(next.version) < Number(snapshot.version)) return;
    snapshot=next;error='';reloadNeeded=false;
    if (!snapshot.active_job_id) stopPolling();
    paint();await syncContent();
  };
  const poll = () => {
    if (stop || !active() || !snapshot.active_job_id) return;
    stop=watchResource({load,initial:snapshot,interval,visibility,update:next=>{void accept(next);},error:cause=>{
      if (cause) fail(cause,true);
      else if (active() && reloadNeeded && !mismatched()) { error='';reloadNeeded=false;paint(); }
    }});
  };
  const read = () => {
    if (reading) return reading;
    controller=new AbortController();
    reading=(async()=>{
      try { const next=await load({signal:controller.signal});await accept(next); }
      catch(cause) { fail(cause,true); }
      finally { reading=undefined;if(active()){loading=false;paint();poll();} }
    })();
    return reading;
  };
  const submitMessage = async event => {
    event.preventDefault();
    if (!active() || busy() || isEditing() || mismatched() || reloadNeeded || !input.value.trim()) { paint();return; }
    const raw=input.value, payload={version:content.version,message:raw.trim(),slot_id:question.value || null,auto_review:getAutoReview() === true};
    const nextFingerprint=JSON.stringify(payload);
    if (fingerprint !== nextFingerprint) { fingerprint=nextFingerprint;requestKey=makeKey(); }
    pending='send';error='';stopPolling();controller=new AbortController();paint();
    try {
      const result=await send({...payload,request_key:requestKey},{signal:controller.signal});
      if (!active()) return;
      if (!result?.job_id) throw new Error('Chat request was not accepted');
      snapshot={...snapshot,active_job_id:result.job_id};
      if (input.value === raw) input.value='';
      fingerprint='';requestKey=undefined;
      await read();
    } catch(cause) { fail(cause); }
    finally { if(active()){pending='';paint();poll();} }
  };
  const clicked = async event => {
    const reconnect=event.target.closest?.('[data-chat-reload]');
    if (reconnect && panel.contains(reconnect)) {
      event.preventDefault();
      if (loading || pending || updating) return;
      loading=true;stopPolling();paint();await read();return;
    }
    const button=event.target.closest?.('[data-chat-undo]');
    if (!button || !panel.contains(button)) return;
    event.preventDefault();
    if (!active() || busy() || isEditing() || mismatched() || reloadNeeded) { paint();return; }
    const message=[...snapshot.messages].reverse().find(item=>item.can_undo && item.version === content.version);
    if (!message || message.id !== button.dataset.chatUndo) return;
    const payload={version:content.version,message_id:message.id}, nextFingerprint=JSON.stringify(payload);
    if (undoFingerprint !== nextFingerprint) { undoFingerprint=nextFingerprint;undoKey=makeKey(); }
    pending='undo';error='';stopPolling();controller=new AbortController();paint();
    try {
      const result=await undo({...payload,request_key:undoKey},{signal:controller.signal});
      if (!active()) return;
      await accept({...snapshot,version:result.version,active_job_id:null});
      undoFingerprint='';undoKey=undefined;await read();
    } catch(cause) { fail(cause); }
    finally { if(active()){pending='';paint();poll();} }
  };
  const inputChanged = () => { if(error && !reloadNeeded)error='';paint(); };
  const keydown = event => {
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229) return;
    event.preventDefault();if(!submit.disabled)form.requestSubmit();
  };
  form.addEventListener('submit',submitMessage);input.addEventListener('input',inputChanged);input.addEventListener('keydown',keydown);panel.addEventListener('click',clicked);
  paint();void read();
  const dispose = () => {
    disposed=true;stopPolling();controller?.abort();
    form.removeEventListener('submit',submitMessage);input.removeEventListener('input',inputChanged);input.removeEventListener('keydown',keydown);panel.removeEventListener('click',clicked);
  };
  dispose.updateContent = next => {
    if (!active()) return;
    content=next;
    const selected=question.value;question.innerHTML=choiceOptions(content);
    question.value=(content.asset?.questions || []).some((item,index)=>questionSlot(item,index) === selected) ? selected : '';
    paint();
  };
  dispose.refresh = () => { paint();if(mismatched() && !isEditing())void syncContent(); };
  dispose.selectQuestion = slotId => {
    if (!active()) return;
    if (!(content.asset?.questions || []).some((item,index)=>questionSlot(item,index) === slotId)) return;
    question.value=slotId;disclosure.open=true;input.focus({preventScroll:true});panel.scrollIntoView({block:'nearest',behavior:'instant'});paint();
  };
  dispose.isBusy=busy;
  return dispose;
}
