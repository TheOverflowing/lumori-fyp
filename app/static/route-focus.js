/* Announce completed navigation through its heading without interrupting the
 * user's next action or the list's more precise restored position and focus. */
export function beginRouteFocus({root, previous, next, signal, window:win = globalThis.window}) {
  const changed = previous && previous.account === next.account &&
    ['route', 'id', 'course'].some(key => (previous[key] || '') !== (next[key] || ''));
  if (!changed || signal?.aborted) return {finish:() => false};

  let settled = false, interrupted = false;
  const events = ['keydown', 'pointerdown', 'touchstart', 'wheel'];
  const interrupt = () => { interrupted = true; };
  const cleanup = () => {
    for (const event of events) win.removeEventListener(event, interrupt, true);
    signal?.removeEventListener('abort', cancel);
  };
  const cancel = () => { settled = true; cleanup(); };
  for (const event of events) win.addEventListener(event, interrupt, {capture:true, passive:true});
  signal?.addEventListener('abort', cancel, {once:true});

  return {
    finish({restored = false} = {}) {
      if (settled) return false;
      settled = true;
      cleanup();
      if (restored || interrupted || signal?.aborted || root.isConnected === false) return false;
      const heading = root.querySelector('h1') || root.querySelector('h2');
      if (!heading) return false;
      if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1');
      heading.focus({preventScroll:true});
      return true;
    },
  };
}
