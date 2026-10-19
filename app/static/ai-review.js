import { a, formatDate, m, setText, t } from './i18n.js';
import { createRequestId } from './request-id.js';
import { watchResource } from './live-updates.js';

const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const running = review => ['queued','running'].includes(review?.status);
const currentReview = content => content.ai_review && content.ai_review.version === content.version && content.ai_review.stale !== true;
const checkNames = {
  source_grounding:'资料依据', grounding:'资料依据', groundedness:'资料依据', source_alignment:'资料一致性', correctness:'内容正确性',
  completeness:'内容完整性', clarity:'表达清晰度', consistency:'内容一致性', answer_correctness:'答案正确性',
  difficulty_alignment:'难度匹配', safety:'内容安全性', structure:'内容结构', answerability:'可作答性', objective_alignment:'学习目标匹配',
};
const resultNames = {pass:'通过',fail:'需修改',uncertain:'待人工判断'};
const severityNames = {critical:'重要问题',high:'重要问题',error:'重要问题',uncertain:'待人工判断',warning:'需关注',medium:'需关注',low:'建议',info:'建议'};
const values = value => Array.isArray(value) ? value : [];

export function approvalLabelKey(content = {}) {
  const approval = content.approval;
  if (content.status === 'approved' && approval?.version === content.version) {
    if (approval.method === 'ai') return 'AI 审核通过';
    if (approval.method === 'manual') return '人工确认';
  }
  return '已确认';
}
export const approvalLabel = content => t(approvalLabelKey(content));

function panelState(content, local = {}) {
  const review = content.ai_review;
  if (local.versionMismatch) return {kind:'uncertain',title:'材料已有新版本',copy:'请刷新材料后再审核；当前编辑内容不会被替换。'};
  if (local.pending) return {kind:'running',title:'正在提交审核',copy:'通过后自动确认当前版本。'};
  if (review && !currentReview(content)) return {kind:'stale',title:'上个版本的审核',copy:'此报告不适用于当前版本，请重新审核。'};
  if (running(review)) return {kind:'running',title:review.status === 'queued' ? 'AI 审核排队中' : 'AI 正在审核',copy:'正在检查内容与资料依据，离开页面后审核仍会继续。'};
  if (review?.status === 'succeeded') {
    if (review.decision === 'approve') return review.applied === true && content.status === 'approved'
      ? {kind:'approved',title:'AI 审核通过',copy:'本次审核已自动确认当前版本。'}
      : {kind:'uncertain',title:'AI 建议通过',copy:'审核报告已保存，但未自动确认当前版本。'};
    if (review.decision === 'revision_required') return {kind:'revision',title:'建议修改后再审核',copy:'请查看下方问题，修改并保存后可再次审核。'};
    return {kind:'uncertain',title:'需要人工判断',copy:'AI 未能作出通过判断，请结合资料检查材料。'};
  }
  if (['failed','cancelled'].includes(review?.status)) return {kind:'failed',title:review.status === 'cancelled' ? 'AI 审核已取消' : 'AI 审核未完成',copy:'本次审核未自动确认材料。你可以重试或人工检查。'};
  return {kind:'idle',title:'AI 审核',copy:content.status === 'draft' ? '通过后自动确认当前版本。' : '此版本的确认方式已记录。'};
}

function unitLabel(id) {
  if (id === 'global') return m('整体材料');
  const match = /^(section|question):([1-9]\d*)$/.exec(String(id ?? ''));
  return match ? m(match[1] === 'section' ? '小节 {n}' : '第 {n} 题',{n:match[2]}) : m('材料内容');
}

function sourceLabels(ids, content) {
  const sources = new Map(values(content.sources).filter(source=>typeof source?.id === 'string').map(source=>[source.id,source]));
  return [...new Set(values(ids))].map(id=>{
    const source=sources.get(id);
    if (!source) return m('来源信息不可用');
    return `${source.document_name ? escape(source.document_name) : m('未命名资料')}${Number.isInteger(source.page) && source.page > 0 ? ` · ${m('第 {n} 页',{n:source.page})}` : ''}`;
  }).join('；');
}

function renderReport(review, content) {
  if (!review) return '';
  const checks = values(review.checks).filter(row=>row && typeof row === 'object');
  const items = values(review.items).filter(row=>row && typeof row === 'object');
  const findings = values(review.findings).filter(row=>row && typeof row === 'object').sort((first,second)=>Number(second.severity === 'error') - Number(first.severity === 'error'));
  const result = row => Object.hasOwn(resultNames,row.status) ? row.status : 'uncertain';
  const check = (row, item = false) => `<li class="ai-review-check" data-result="${result(row)}"><div><strong>${item ? unitLabel(row.id) : Object.hasOwn(checkNames,row.key) ? m(checkNames[row.key]) : escape(row.key || t('审核项目'))}</strong><span class="ai-review-result">${m(resultNames[result(row)])}</span></div>${row.rationale ? `<p>${escape(row.rationale)}</p>` : ''}${item && values(row.evidence).length ? `<div class="ai-review-item-evidence">${values(row.evidence).filter(evidence=>evidence && typeof evidence === 'object').map(evidence=>`<p>${sourceLabels([evidence.source_id],content)}</p><blockquote>${escape(evidence.quote)}</blockquote>`).join('')}</div>` : ''}</li>`;
  const finding = (row,index) => `<li><div class="ai-review-finding-label">${m(Object.hasOwn(severityNames,row.severity) ? severityNames[row.severity] : '需关注')}${row.unit_id ? `<span>${unitLabel(row.unit_id)}</span>` : ''}</div><p>${escape(row.message)}</p>${row.suggestion ? `<p class="ai-review-suggestion">${m('修改建议')}<span>${escape(row.suggestion)}</span></p>` : ''}${row.quote || values(row.source_ids).length ? `<details class="ai-review-finding-context" data-ai-review-disclosure="finding-${index}"><summary>${m('查看问题原文与来源')}</summary>${row.quote ? `<blockquote>${escape(row.quote)}</blockquote>` : ''}${values(row.source_ids).length ? `<p class="ai-review-source-ids">${m('参考资料')}<span>${sourceLabels(row.source_ids,content)}</span></p>` : ''}</details>` : ''}</li>`;
  const date = review.created_at && formatDate(review.created_at);
  return `<div class="ai-review-report">${review.summary ? `<p class="ai-review-summary">${escape(review.summary)}</p>` : ''}
    ${findings.length ? `<section class="ai-review-findings"><h4>${m('需要关注')}<span>${m('{n} 项',{n:findings.length})}</span></h4><ol>${findings.slice(0,3).map(finding).join('')}</ol>${findings.length > 3 ? `<details class="ai-review-more-findings" data-ai-review-disclosure="more-findings"><summary>${m('查看其余 {n} 项问题',{n:findings.length-3})}</summary><ol start="4">${findings.slice(3).map((row,index)=>finding(row,index+3)).join('')}</ol></details>` : ''}</section>` : ''}
    ${checks.length || items.length ? `<details class="ai-review-evidence" data-ai-review-disclosure="evidence"><summary>${m('查看审核依据')}</summary>${checks.length ? `<ul class="ai-review-checks">${checks.map(row=>check(row)).join('')}</ul>` : ''}${items.length ? `<section class="ai-review-items"><h4>${m('逐项审核记录')}<span>${m('{n} 项',{n:items.length})}</span></h4><ul class="ai-review-checks">${items.map(row=>check(row,true)).join('')}</ul></section>` : ''}${review.version != null || date || review.model ? `<p class="ai-review-report-meta">${review.version != null ? m('审核版本 {n}',{n:review.version}) : ''}${date ? `<time datetime="${escape(review.created_at)}" data-date="${escape(review.created_at)}">${escape(date)}</time>` : ''}${review.model ? `<span>${escape(review.model)}</span>` : ''}</p>` : ''}</details>` : ''}
  </div>`;
}

function panelBody(content, local = {}) {
  const state = panelState(content,local), review = content.ai_review;
  const canStart = content.status === 'draft';
  const blocked = local.pending || local.editing || local.versionMismatch || (currentReview(content) && running(review));
  const retry = review && currentReview(content) && ['failed','cancelled'].includes(review.status);
  const action = local.error ? '重试提交审核' : retry ? '重新审核' : review ? '再次 AI 审核' : '开始 AI 审核';
  const provenance = content.status === 'approved' ? `<p class="ai-review-provenance">${m('当前版本')}<strong>${m(approvalLabelKey(content))}</strong></p>` : '';
  const backendError = ['failed','cancelled'].includes(review?.status) && (typeof review.error === 'string' ? review.error : review.error?.message);
  return `<div class="ai-review-topline"><div class="ai-review-heading"><div class="ai-review-symbol" aria-hidden="true">${state.kind === 'running' ? '<span class="ai-review-spinner"></span>' : `<img src="/static/icons/${state.kind === 'approved' ? 'check' : 'file-text'}.svg" alt="">`}</div><div><h3>${m(state.title)}</h3><p>${m(state.copy)}</p></div></div>
    ${canStart ? `<div class="ai-review-actions"><button type="button" class="secondary" data-ai-review-start ${blocked ? 'disabled' : ''}>${m(local.pending ? '正在提交…' : currentReview(content) && running(review) ? '审核进行中' : action)}</button></div>` : ''}</div>
    ${provenance}${local.editing && canStart ? `<p class="ai-review-edit-note">${m('请先保存或收起编辑，再审核已保存的版本。')}</p>` : ''}
    ${backendError ? `<p class="ai-review-error ai-review-backend-error" role="alert">${m(backendError)}</p>` : ''}
    <p class="ai-review-error" data-ai-review-error role="alert" ${local.error ? '' : 'hidden'}>${local.error ? m(local.error) : ''}</p>
    ${renderReport(review,content)}<p class="ai-review-disclaimer">${m('AI 审核不等同于教师确认。')}</p>`;
}

export function renderAiReviewPanel(content = {}) {
  return `<section class="ai-review-panel" data-ai-review-panel data-state="${panelState(content).kind}" ${a('AI 审核','aria-label')}><div data-ai-review-body>${panelBody(content)}</div><p class="sr-only" data-ai-review-live role="status" aria-live="polite" aria-atomic="true"></p></section>`;
}

// Only this panel is repainted. The caller updates approval controls without replacing an open editor.
export function bindAiReviewPanel(root, initial, {start,load,onUpdated=()=>{},onError=()=>{},isEditing=()=>false,isActive=()=>true,interval=3000,visibility=document,makeKey=()=>createRequestId()} = {}) {
  const panel = root.matches?.('[data-ai-review-panel]') ? root : root.querySelector('[data-ai-review-panel]');
  if (!panel) return Object.assign(()=>{}, {refresh(){}});
  const body = panel.querySelector('[data-ai-review-body]'), live = panel.querySelector('[data-ai-review-live]');
  let content=initial, disposed=false, pending=false, requestKey, controller, stop, epoch=0, error='', versionMismatch=false;
  const active = token => !disposed && panel.isConnected !== false && isActive() && (token === undefined || token === epoch);
  const stopPolling = () => { stop?.(); stop=undefined; };
  const paint = () => {
    if (!active()) return;
    const expanded = new Set([...(body.querySelectorAll?.('[data-ai-review-disclosure]') || [])].filter(node=>node.open).map(node=>node.dataset.aiReviewDisclosure));
    const local={pending,error,versionMismatch,editing:isEditing()}, state=panelState(content,local);
    body.innerHTML=panelBody(content,local); panel.dataset.state=state.kind;
    for (const node of body.querySelectorAll?.('[data-ai-review-disclosure]') || []) node.open=expanded.has(node.dataset.aiReviewDisclosure);
    if (live && live.dataset.i18n !== state.title) setText(live,state.title);
  };
  const fail = cause => {
    if (!active() || ['AbortError','SessionChangedError'].includes(cause?.name)) return;
    const actionable = cause?.uiMessage || ([400,409,422].includes(cause?.status) && typeof cause?.message === 'string' ? cause.message : null);
    error=actionable || '暂时无法连接审核服务。请重试，材料的确认状态不会因此改变。';
    paint(); onError(cause);
  };
  const accept = (next, token) => {
    if (!active(token) || !next || next.id !== content.id) return false;
    if (next.version !== content.version) {
      // A newer saved document must never replace an editor's local version.
      if (Number(next.version) > Number(content.version)) { versionMismatch=true;stopPolling();paint(); }
      return false;
    }
    content=next;error='';
    if (!running(content.ai_review) || !currentReview(content)) { requestKey=undefined;stopPolling(); }
    paint();onUpdated(next);return true;
  };
  const poll = () => {
    if (stop || !active() || versionMismatch || !currentReview(content) || !running(content.ai_review)) return;
    const token=epoch;
    stop=watchResource({load,initial:content,interval,visibility,update:next=>accept(next,token),error:cause=>{
      if (!active(token)) return;
      if (cause) fail(cause); else if (error) { error='';paint(); }
    }});
  };
  const send = async event => {
    const control=event.target.closest?.('[data-ai-review-start]');
    if (!control || !panel.contains(control)) return;
    event.preventDefault();
    if (!active() || pending || versionMismatch || content.status !== 'draft' || isEditing() || (currentReview(content) && running(content.ai_review))) { paint();return; }
    const token=epoch, version=content.version;
    if (!Number.isInteger(version) || version < 1) { error='材料版本无效，请刷新后再审核。';paint();return; }
    stopPolling();pending=true;error='';controller=new AbortController();
    paint();
    try {
      requestKey ||= makeKey();
      const result=await start({version,request_key:requestKey},{signal:controller.signal});
      if (!active(token)) return;
      const returned=result?.content || (result?.ai_review ? result : null);
      if (returned) {
        if (!accept(returned,token)) throw new Error('Review response did not match the current material.');
      } else {
        if (!result?.job_id) throw new Error('Review task was not created.');
        content={...content,ai_review:{job_id:result.job_id,version,status:'queued'}};
      }
      if (!active(token)) return;
      pending=false;paint();
      try { accept(await load({signal:controller.signal}),token); } catch(cause) { if(active(token))fail(cause); }
    } catch(cause) { if(active(token))fail(cause); }
    finally { if(active(token)) { pending=false;controller=undefined;paint();poll(); } }
  };
  panel.addEventListener('click',send);paint();poll();
  const dispose = () => { disposed=true;epoch++;stopPolling();controller?.abort();panel.removeEventListener('click',send); };
  dispose.refresh = next => {
    if (!active()) return;
    if (next && (next.id !== content.id || next.version !== content.version)) {
      epoch++;stopPolling();controller?.abort();controller=undefined;pending=false;requestKey=undefined;versionMismatch=false;error='';
    }
    if (next) content=next;
    if (!currentReview(content) || !running(content.ai_review)) {
      stopPolling();
      // Refreshing edit controls must preserve a request with an uncertain response.
      if (next?.ai_review?.job_id && currentReview(next) && !running(next.ai_review)) requestKey=undefined;
    }
    paint();poll();
  };
  return dispose;
}
