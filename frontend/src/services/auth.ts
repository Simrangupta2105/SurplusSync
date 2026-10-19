/**
 * SurplusSync Auth Token Manager
 * - JWT access token kept purely IN MEMORY (never persisted to localStorage/sessionStorage)
 * - Refresh token stored in localStorage if "Remember Me" is true, else sessionStorage
 * - Tokens are NEVER logged to console or exposed
 * - Single-flight refresh mutex
 */

const REFRESH_TOKEN_KEY = 'surplussync_rf_token';
const REMEMBER_ME_KEY = 'surplussync_remember_me';

let inMemoryAccessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;

type AuthChangeCallback = (isAuthenticated: boolean) => void;
const listeners = new Set<AuthChangeCallback>();

export function subscribeAuth(cb: AuthChangeCallback): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function notifyAuthChange(isAuthenticated: boolean) {
  listeners.forEach((cb) => {
    try {
      cb(isAuthenticated);
    } catch {
      // Ignore listener error
    }
  });
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getStoredRefreshToken(): string | null {
  try {
    const isRemembered = localStorage.getItem(REMEMBER_ME_KEY) === 'true';
    if (isRemembered) {
      return localStorage.getItem(REFRESH_TOKEN_KEY);
    }
    return sessionStorage.getItem(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function storeTokens(access: string, refresh: string, rememberMe = false): void {
  inMemoryAccessToken = access;
  try {
    if (rememberMe) {
      localStorage.setItem(REMEMBER_ME_KEY, 'true');
      localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
      sessionStorage.removeItem(REFRESH_TOKEN_KEY);
    } else {
      localStorage.removeItem(REMEMBER_ME_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      sessionStorage.setItem(REFRESH_TOKEN_KEY, refresh);
    }
    notifyAuthChange(true);
  } catch {
    // Storage access may be restricted
  }
}

export function clearAuthSession(): void {
  inMemoryAccessToken = null;
  try {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(REMEMBER_ME_KEY);
    sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    // Ignore
  }
  notifyAuthChange(false);
}

export function isAuthenticated(): boolean {
  return inMemoryAccessToken !== null || getStoredRefreshToken() !== null;
}

/**
 * Perform single-flight token refresh using the stored refresh token
 */
export async function refreshAccessToken(
  refreshEndpoint: (refresh: string) => Promise<{ access: string }>
): Promise<string | null> {
  if (refreshPromise) {
    return refreshPromise;
  }

  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    clearAuthSession();
    return null;
  }

  refreshPromise = (async () => {
    try {
      const res = await refreshEndpoint(refreshToken);
      if (res && res.access) {
        inMemoryAccessToken = res.access;
        return res.access;
      }
      clearAuthSession();
      return null;
    } catch {
      clearAuthSession();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}
