import { computed } from 'vue';

export function useAuth() {
  const config = useRuntimeConfig();
  const authToken = useState<string>('authToken', () => '');
  const authUser = useState<any>('authUser', () => null);
  const authOpen = useState<boolean>('authOpen', () => false);
  const authMode = useState<string>('authMode', () => 'login');
  const authEmail = useState<string>('authEmail', () => '');
  const authPassword = useState<string>('authPassword', () => '');
  const authError = useState<string>('authError', () => '');
  const authInit = useState<boolean>('authInit', () => false);

  const isAuthenticated = computed(() => !!authToken.value && !!authUser.value);
  const authHeaders = computed(() =>
    authToken.value ? { Authorization: `Bearer ${authToken.value}` } : {}
  );

  if (process.client && !authInit.value) {
    authInit.value = true;
    const storedToken = localStorage.getItem('lumen.authToken');
    const storedUser = localStorage.getItem('lumen.authUser');
    if (storedToken) authToken.value = storedToken;
    if (storedUser) {
      try {
        authUser.value = JSON.parse(storedUser);
      } catch (_) {
        authUser.value = null;
      }
    }
  }

  function persistAuth(token: string, user: any) {
    authToken.value = token;
    authUser.value = user;
    if (process.client) {
      localStorage.setItem('lumen.authToken', token);
      localStorage.setItem('lumen.authUser', JSON.stringify(user));
    }
  }

  function clearAuth() {
    authToken.value = '';
    authUser.value = null;
    if (process.client) {
      localStorage.removeItem('lumen.authToken');
      localStorage.removeItem('lumen.authUser');
    }
  }

  async function signup() {
    authError.value = '';
    try {
      const data = await $fetch(`${config.public.apiBase}/auth/signup`, {
        method: 'POST',
        body: { email: authEmail.value, password: authPassword.value }
      });
      persistAuth(data.access_token, data.user);
      authPassword.value = '';
      authOpen.value = false;
    } catch (err: any) {
      authError.value = err?.data?.detail || 'Signup failed';
    }
  }

  async function login() {
    authError.value = '';
    try {
      const data = await $fetch(`${config.public.apiBase}/auth/login`, {
        method: 'POST',
        body: { email: authEmail.value, password: authPassword.value }
      });
      persistAuth(data.access_token, data.user);
      authPassword.value = '';
      authOpen.value = false;
    } catch (err: any) {
      authError.value = err?.data?.detail || 'Login failed';
    }
  }

  function logout() {
    clearAuth();
    authOpen.value = false;
  }

  function openAuth(mode: string) {
    authMode.value = mode;
    authError.value = '';
    authOpen.value = true;
  }

  return {
    authToken,
    authUser,
    authOpen,
    authMode,
    authEmail,
    authPassword,
    authError,
    isAuthenticated,
    authHeaders,
    signup,
    login,
    logout,
    openAuth
  };
}
