import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  storeTokens,
  getAccessToken,
  getStoredRefreshToken,
  clearAuthSession,
  refreshAccessToken,
  isAuthenticated,
} from '../services/auth';

describe('Auth & Token Manager (In-Memory Access + Refresh Mutex)', () => {
  beforeEach(() => {
    clearAuthSession();
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('keeps access token purely in-memory and never in localStorage or sessionStorage', () => {
    storeTokens('jwt-access-abc', 'jwt-refresh-xyz', true);

    expect(getAccessToken()).toBe('jwt-access-abc');
    expect(localStorage.getItem('jwt-access-abc')).toBeNull();
    expect(sessionStorage.getItem('jwt-access-abc')).toBeNull();
  });

  it('stores refresh token in localStorage when rememberMe is true', () => {
    storeTokens('access-123', 'refresh-remembered', true);

    expect(localStorage.getItem('surplussync_rf_token')).toBe('refresh-remembered');
    expect(localStorage.getItem('surplussync_remember_me')).toBe('true');
    expect(sessionStorage.getItem('surplussync_rf_token')).toBeNull();
    expect(getStoredRefreshToken()).toBe('refresh-remembered');
  });

  it('stores refresh token in sessionStorage when rememberMe is false', () => {
    storeTokens('access-123', 'refresh-session-only', false);

    expect(sessionStorage.getItem('surplussync_rf_token')).toBe('refresh-session-only');
    expect(localStorage.getItem('surplussync_rf_token')).toBeNull();
    expect(getStoredRefreshToken()).toBe('refresh-session-only');
  });

  it('clears all session and local storage on logout/session expiry', () => {
    storeTokens('access-123', 'refresh-abc', true);
    expect(isAuthenticated()).toBe(true);

    clearAuthSession();

    expect(getAccessToken()).toBeNull();
    expect(getStoredRefreshToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it('refreshes token successfully and updates in-memory access token', async () => {
    storeTokens('expired-access', 'valid-refresh-token', true);

    const mockRefreshEndpoint = vi.fn().mockResolvedValue({
      access: 'new-fresh-access-token',
    });

    const refreshed = await refreshAccessToken(mockRefreshEndpoint);

    expect(mockRefreshEndpoint).toHaveBeenCalledWith('valid-refresh-token');
    expect(refreshed).toBe('new-fresh-access-token');
    expect(getAccessToken()).toBe('new-fresh-access-token');
  });

  it('clears session when refresh token fails', async () => {
    storeTokens('expired-access', 'invalid-refresh-token', true);

    const mockRefreshEndpoint = vi.fn().mockRejectedValue(new Error('Invalid token'));

    const refreshed = await refreshAccessToken(mockRefreshEndpoint);

    expect(refreshed).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(getStoredRefreshToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it('ensures single-flight concurrency: only one refresh call is in flight at a time', async () => {
    storeTokens('expired-access', 'valid-refresh', true);

    let resolvePromise: (val: { access: string }) => void;
    const pendingPromise = new Promise<{ access: string }>((resolve) => {
      resolvePromise = resolve;
    });

    const mockRefreshEndpoint = vi.fn().mockReturnValue(pendingPromise);

    // Call refresh simultaneously twice
    const call1 = refreshAccessToken(mockRefreshEndpoint);
    const call2 = refreshAccessToken(mockRefreshEndpoint);

    // Endpoint should be called only once
    expect(mockRefreshEndpoint).toHaveBeenCalledTimes(1);

    resolvePromise!({ access: 'concurrent-refreshed-token' });

    const [res1, res2] = await Promise.all([call1, call2]);
    expect(res1).toBe('concurrent-refreshed-token');
    expect(res2).toBe('concurrent-refreshed-token');
  });
});
