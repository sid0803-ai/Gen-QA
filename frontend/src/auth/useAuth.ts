import * as authApi from '../api/auth';
import { useAuthStore } from '../store/authStore';
import type { User } from '../api/types';

/**
 * useAuth() — the app's public auth API surface.
 *
 * State lives in the zustand `authStore` (tokens + user + selected project);
 * this hook exposes the current user plus the login/register/logout actions
 * that components should call, matching the AuthContext-shaped API the
 * rest of the app expects.
 */
export function useAuth() {
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);
  const storeLogout = useAuthStore((s) => s.logout);

  const login = async (email: string, password: string): Promise<User> => {
    const tokens = await authApi.login(email, password);
    setTokens(tokens);
    const currentUser = await authApi.me();
    setUser(currentUser);
    return currentUser;
  };

  const register = async (
    email: string,
    password: string,
    fullName: string,
  ): Promise<User> => {
    await authApi.register(email, password, fullName);
    // Registration doesn't return tokens, so log in right after for a
    // smooth "register -> land in the app" flow.
    return login(email, password);
  };

  const logout = () => {
    storeLogout();
  };

  return {
    user,
    isAuthenticated: !!accessToken,
    login,
    register,
    logout,
  };
}
