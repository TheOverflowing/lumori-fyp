export function consumeDemoLink(location, history) {
  if (!location.hash.startsWith('#demo?')) return null;
  const token = new URLSearchParams(location.hash.slice(6)).get('token') || '';
  // Remove the bearer from the address before any authenticated navigation.
  history.replaceState(null, '', location.pathname + location.search + '#documents');
  return token;
}
