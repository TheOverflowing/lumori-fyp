export function readSessionBootstrap(document) {
  const element = document.getElementById('session-bootstrap');
  const raw = element?.textContent;
  element?.remove();
  try { return JSON.parse(raw); }
  catch { return {user:null, csrf_token:null}; }
}

export function sessionChangeRequiresReset(value, currentUserId) {
  try {
    const signal = JSON.parse(value);
    if (signal && Object.hasOwn(signal, 'userId')) return signal.userId !== (currentUserId || null);
  } catch { /* Older tabs sent plain nonces. */ }
  return true;
}
