import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AuthTokens, User } from '../api/types';

/**
 * Local/UI state only: tokens, current user, and the selected project id.
 * Server data (project lists, members, etc.) lives in React Query, not here.
 *
 * V1 simplification: tokens are persisted to localStorage via zustand's
 * `persist` middleware. This is convenient for a first pass but is not a
 * security-final decision — localStorage is readable by any script on the
 * page (XSS risk). A later sprint should consider httpOnly cookies or
 * in-memory tokens with silent refresh instead.
 */
interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  selectedProjectId: string | null;
  setTokens: (tokens: AuthTokens) => void;
  setUser: (user: User | null) => void;
  setSelectedProjectId: (projectId: string | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      selectedProjectId: null,
      setTokens: (tokens) =>
        set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token }),
      setUser: (user) => set({ user }),
      setSelectedProjectId: (projectId) => set({ selectedProjectId: projectId }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    {
      name: 'genqa-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        selectedProjectId: state.selectedProjectId,
      }),
    },
  ),
);
