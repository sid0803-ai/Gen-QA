import { useEffect, useState, type ReactNode } from 'react';
import { Spin } from 'antd';
import * as authApi from '../api/auth';
import { useAuthStore } from '../store/authStore';

/**
 * Bootstraps auth on page load: if we have a persisted access token but no
 * user in memory (e.g. after a hard refresh), fetch /auth/me to repopulate
 * it. If that fails, the api client's 401 handling will have already tried
 * a refresh; a final failure here just logs the user out.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);
  const [checking, setChecking] = useState(() => !!accessToken && !user);

  useEffect(() => {
    let cancelled = false;

    if (!accessToken || user) {
      setChecking(false);
      return;
    }

    authApi
      .me()
      .then((currentUser) => {
        if (!cancelled) setUser(currentUser);
      })
      .catch(() => {
        if (!cancelled) logout();
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });

    return () => {
      cancelled = true;
    };
    // Only run on mount: this is a one-time bootstrap check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (checking) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  return <>{children}</>;
}
