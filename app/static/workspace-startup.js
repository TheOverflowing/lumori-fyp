/* Inlined after the HTML shell: no network request or login-status check. */
(() => {
  let session;
  try { session=JSON.parse(document.getElementById('session-bootstrap')?.textContent || 'null'); }
  catch { return; }
  if (!session?.user?.id || !session.csrf_token) return;
  // A demo link may switch away from a different account; keep that account hidden.
  if (location.hash.startsWith('#demo?') && !session.demo_course_id) return;
  document.querySelector('.app-shell').hidden=false;
  document.querySelector('.skip').hidden=false;
  document.getElementById('auth-gate').hidden=true;
  const name=session.user.display_name || session.user.email;
  document.getElementById('account-name').textContent=name;
  document.getElementById('account-initial').textContent=[...name].slice(0,1).join('').toUpperCase();
  document.getElementById('account-button').title=session.user.email;
})();
