import { m } from './i18n.js';
import { renderMascot } from './mascot-feedback.js';

const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const icon = name => `<img src="/static/icons/${name}.svg" alt="" aria-hidden="true">`;

// Readiness describes usable course sources, never a claim about output quality.
export function courseOverview(documents = [], contents = []) {
  const documentsInCourse = documents.filter(doc => !doc.deleted_at);
  const ready = documentsInCourse.filter(doc => doc.index_current && doc.enabled !== false).length;
  const drafts = contents.filter(content => content.status === 'draft').length;
  return {
    documents:documentsInCourse.length, ready, materials:contents.length, drafts,
    action:!documentsInCourse.length ? 'upload' : !ready ? 'documents' : 'generate',
    actionLabel:!documentsInCourse.length ? '导入第一份资料' : !ready ? '准备课程资料' : '开始新的创作',
  };
}

export function renderStudioIntro({course, documents, contents}) {
  const overview = courseOverview(documents, contents);
  return `<header class="studio-heading"><div><span class="studio-eyebrow">${m('你的教学工作台')}</span><h1>${escape(course.name)}</h1></div><span class="studio-edition" aria-hidden="true">LUMORI / STUDIO</span></header>
    <section class="studio-hero" aria-labelledby="studio-hero-title">
      <div class="studio-hero-copy"><span class="studio-kicker">${m('源于课程，成于你的判断')}</span><h2 id="studio-hero-title">${m('让知识，')}<br>${m('成为启发。')}</h2><p>${m('从一份资料，到一堂有依据的好课。')}</p><div class="studio-hero-actions"><button data-action="${overview.action}" class="studio-primary">${m(overview.actionLabel)}${icon('arrow-right')}</button>${overview.drafts ? `<button data-action="contents" class="studio-review">${m('审核待确认材料')}${icon('arrow-up-right')}</button>` : ''}</div></div>
      <div class="studio-art" aria-hidden="true">${renderMascot('welcome','studio-companion')}<span class="studio-art-caption">${m('每一次启发，都有迹可循。')}</span></div>
    </section>
    <section class="studio-path" aria-label="${escape('Lumori')}">
      <button data-action="documents" class="studio-path-step"><span class="studio-step-index">01</span><span class="studio-step-copy"><strong>${m('课程资料')}</strong><small>${m('{n} 份可用资料',{n:overview.ready})}</small></span>${icon('arrow-up-right')}</button>
      <button data-action="generate" class="studio-path-step"><span class="studio-step-index">02</span><span class="studio-step-copy"><strong>${m('创作学习材料')}</strong><small>${m('{n} 份已创作材料',{n:overview.materials})}</small></span>${icon('arrow-up-right')}</button>
      <button data-action="contents" class="studio-path-step"><span class="studio-step-index">03</span><span class="studio-step-copy"><strong>${m('内容与审核')}</strong><small>${m(overview.drafts ? '{n} 份材料待审核' : overview.materials ? '暂无待审核材料' : '等待第一份材料',{n:overview.drafts})}</small></span>${overview.drafts ? `<span class="studio-review-count" aria-hidden="true">${overview.drafts}</span>` : icon('arrow-up-right')}</button>
    </section>`;
}

export function renderStudioChoices() {
  const choices = [
    ['lesson','book-open','学习讲解','让复杂概念，循序展开'],
    ['quiz','check-square','测验练习','用恰当的问题，检验理解'],
    ['assignment','file-text','课后作业','把课堂所学，带入实践'],
  ];
  return `<div class="heading-row studio-section-heading"><h2>${m('今天，想创作什么？')}</h2><span>${m('选择一种材料，开始你的构思')}</span></div><div class="quick-create">${choices.map(([kind,symbol,label,description])=>`<button class="create-choice studio-choice" data-action="create-kind" data-kind="${kind}"><span class="studio-choice-icon">${icon(symbol)}</span><span class="studio-choice-copy"><strong>${m(label)}</strong><small>${m(description)}</small></span><img class="choice-arrow" src="/static/icons/arrow-up-right.svg" alt=""></button>`).join('')}</div>`;
}
