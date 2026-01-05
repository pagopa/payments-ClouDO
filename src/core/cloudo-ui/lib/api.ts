export const API_URL = '/api/proxy';

export async function cloudoFetch(url: string, options: RequestInit = {}) {
  let currentUser = null;
  if (typeof window !== 'undefined') {
    const expiresAt = localStorage.getItem('cloudo_expires_at');
    const auth = localStorage.getItem('cloudo_auth');

    if (auth === 'true' && !expiresAt) {
      localStorage.removeItem('cloudo_auth');
      localStorage.removeItem('cloudo_user');
      localStorage.removeItem('cloudo_expires_at');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
      throw new Error('Security protocol violated: Session expiration missing');
    }

    if (expiresAt) {
      const now = new Date();
      const expirationDate = new Date(expiresAt);
      if (now >= expirationDate) {
        // Session expired
        localStorage.removeItem('cloudo_auth');
        localStorage.removeItem('cloudo_user');
        localStorage.removeItem('cloudo_expires_at');
        // Force redirect to login if not already there
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
        throw new Error('Session expired');
      }
    }

    const userData = localStorage.getItem('cloudo_user');
    currentUser = userData ? JSON.parse(userData) : null;
  }

  const headers: Record<string, string> = {
    ...Object.fromEntries(Object.entries(options.headers || {})),
  };

  if (currentUser?.username && !headers['x-cloudo-user']) {
    headers['x-cloudo-user'] = currentUser.username;
  }

  const urlObj = new URL(url, 'http://localhost');
  const targetPath = urlObj.pathname;
  const proxyUrl = `${API_URL}?path=${encodeURIComponent(targetPath)}`;

  let finalProxyUrl = proxyUrl;
  const queryString = urlObj.search.startsWith('?') ? urlObj.search.substring(1) : urlObj.search;
  if (queryString) {
    finalProxyUrl += `&${queryString}`;
  }

  return fetch(finalProxyUrl, {
    ...options,
    headers,
  });
}
