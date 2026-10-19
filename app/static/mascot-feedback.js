// Decorative feedback accompanies the existing status copy and controls.
const poses = {
  welcome:'lumori-companion.svg',
  reading:'lumori-companion-reading.svg',
  celebrate:'lumori-companion-celebrate.svg',
};

export function renderMascot(pose = 'welcome', className = '') {
  const selected = Object.hasOwn(poses,pose) ? pose : 'welcome';
  return `<span class="mascot-feedback mascot-feedback--${selected}${className ? ` ${className}` : ''}" aria-hidden="true"><img src="/static/assets/${poses[selected]}" width="180" height="180" alt="" decoding="async"></span>`;
}

// The existing parent data-state selects the pose in CSS. No task state is
// inferred, and live updates keep these decorative layers mounted.
export function renderProgressMascot() {
  return `<div class="generation-feedback" aria-hidden="true">${renderMascot('reading','generation-feedback-reading')}${renderMascot('celebrate','generation-feedback-celebrate')}${renderMascot('welcome','generation-feedback-rest')}</div>`;
}
