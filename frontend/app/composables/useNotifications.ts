export type ToastType = 'error' | 'success' | 'info';

type Toast = {
  id: string;
  message: string;
  type: ToastType;
};

export function useNotifications() {
  const authBanner = useState<string>('authBanner', () => '');
  const toasts = useState<Toast[]>('toasts', () => []);

  const showAuthBanner = (message: string) => {
    authBanner.value = message;
  };

  const clearAuthBanner = () => {
    authBanner.value = '';
  };

  const removeToast = (id: string) => {
    toasts.value = toasts.value.filter((toast) => toast.id !== id);
  };

  const addToast = (message: string, type: ToastType = 'error', timeoutMs = 5000) => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    toasts.value = [...toasts.value, { id, message, type }];
    if (timeoutMs > 0 && process.client) {
      window.setTimeout(() => removeToast(id), timeoutMs);
    }
  };

  return {
    authBanner,
    toasts,
    showAuthBanner,
    clearAuthBanner,
    addToast,
    removeToast,
  };
}
