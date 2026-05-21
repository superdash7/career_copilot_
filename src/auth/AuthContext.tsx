/* Hooks live next to provider; fast-refresh rule expects components-only files. */
/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  fetchMe,
  login as loginApi,
  register as registerApi,
  storeAuthTokens,
  clearStoredAuthTokens,
  revokeRefreshOnServer,
  ApiError,
  AUTH_ACCESS_STORAGE_KEY,
} from '../api/client';
import type { UserProfile, SessionInvalidReason } from '../types';

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  status: AuthStatus;
  isAuthenticated: boolean;
  loading: boolean;
  token: string | null;
  user: UserProfile | null;
  sessionInvalidReason: SessionInvalidReason;
  clearSessionInvalidReason: () => void;
  setAuthSession: (accessToken: string, refreshToken: string, user: UserProfile) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [sessionInvalidReason, setSessionInvalidReason] = useState<SessionInvalidReason>(null);

  const clearSessionInvalidReason = useCallback(() => setSessionInvalidReason(null), []);

  const setAuthSession = useCallback((accessToken: string, refreshToken: string, nextUser: UserProfile) => {
    storeAuthTokens(accessToken, refreshToken);
    setToken(accessToken);
    setUser(nextUser);
    setSessionInvalidReason(null);
    setStatus('authenticated');
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await loginApi({ email, password });
      setAuthSession(data.access_token, data.refresh_token, data.user);
    },
    [setAuthSession],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      const data = await registerApi({ email, password });
      setAuthSession(data.access_token, data.refresh_token, data.user);
    },
    [setAuthSession],
  );

  const logout = useCallback(() => {
    void revokeRefreshOnServer();
    clearStoredAuthTokens();
    setToken(null);
    setUser(null);
    setSessionInvalidReason(null);
    setStatus('unauthenticated');
  }, []);

  const refreshMe = useCallback(async () => {
    const storedToken = localStorage.getItem(AUTH_ACCESS_STORAGE_KEY);
    if (!storedToken) {
      clearStoredAuthTokens();
      setToken(null);
      setUser(null);
      setSessionInvalidReason(null);
      setStatus('unauthenticated');
      return;
    }
    try {
      const me = await fetchMe();
      setToken(storedToken);
      setUser(me);
      setSessionInvalidReason(null);
      setStatus('authenticated');
    } catch (err) {
      await revokeRefreshOnServer();
      clearStoredAuthTokens();
      setToken(null);
      setUser(null);
      setStatus('unauthenticated');
      if (err instanceof ApiError && err.code === 'USER_NOT_FOUND') {
        setSessionInvalidReason('stale_session');
      } else if (err instanceof ApiError && err.status === 401) {
        setSessionInvalidReason('session_expired');
      } else {
        setSessionInvalidReason(null);
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) void refreshMe();
    });
    return () => {
      cancelled = true;
    };
  }, [refreshMe]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      isAuthenticated: status === 'authenticated',
      loading: status === 'loading',
      token,
      user,
      sessionInvalidReason,
      clearSessionInvalidReason,
      setAuthSession,
      login,
      register,
      logout,
      refreshMe,
    }),
    [
      status,
      token,
      user,
      sessionInvalidReason,
      clearSessionInvalidReason,
      setAuthSession,
      login,
      register,
      logout,
      refreshMe,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth должен вызываться внутри AuthProvider');
  return ctx;
}
