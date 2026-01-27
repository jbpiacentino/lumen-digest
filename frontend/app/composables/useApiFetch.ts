import type { FetchOptions } from 'ofetch';

export function useApiFetch() {
  const { showAuthBanner, addToast } = useNotifications();
  const authToken = useState<string>('authToken', () => '');
  const authUser = useState<any>('authUser', () => null);
  const authOpen = useState<boolean>('authOpen', () => false);

  return async function apiFetch<T>(url: string, options?: FetchOptions<'json'>): Promise<T> {
    try {
      return await $fetch<T>(url, options);
    } catch (err: any) {
      const status = err?.status || err?.response?.status;
      const isAuthEndpoint = typeof url === 'string' && url.includes('/auth/');
      if (status === 401 || status === 403) {
        if (!isAuthEndpoint && authToken.value) {
          showAuthBanner('Session expired. Please sign in again.');
          authToken.value = '';
          authUser.value = null;
          authOpen.value = false;
          if (process.client) {
            localStorage.removeItem('lumen.authToken');
            localStorage.removeItem('lumen.authUser');
          }
        }
      } else {
        const message = err?.data?.detail || err?.message || 'Network error';
        addToast(message, 'error');
      }
      throw err;
    }
  };
}
