import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authApi, usersApi } from "../api/auth";
import { clearTokens, TOKEN_STORAGE_KEY } from "../api/client";
import type { AuthResponse, LoginRequest, RegisterRequest, UpdateProfileRequest, User } from "../types/auth";

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginRequest) => Promise<User>;
  register: (payload: RegisterRequest) => Promise<User>;
  logout: () => void;
  refreshMe: () => Promise<User | null>;
  updateUser: (payload: UpdateProfileRequest) => Promise<User>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const applySession = useCallback((response: AuthResponse) => {
    setUser(response.user);
    return response.user;
  }, []);

  useEffect(() => {
    let cancelled = false;
    const boot = async () => {
      if (!localStorage.getItem(TOKEN_STORAGE_KEY)) {
        setIsLoading(false);
        return;
      }
      try {
        const me = await authApi.me();
        if (!cancelled) setUser(me);
      } catch {
        clearTokens();
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    boot();

    const onUnauthorized = () => {
      setUser(null);
      clearTokens();
    };
    window.addEventListener("vision3d:unauthorized", onUnauthorized);
    return () => {
      cancelled = true;
      window.removeEventListener("vision3d:unauthorized", onUnauthorized);
    };
  }, []);

  const login = useCallback(
    async (payload: LoginRequest) => applySession(await authApi.login(payload)),
    [applySession],
  );

  const register = useCallback(
    async (payload: RegisterRequest) => applySession(await authApi.register(payload)),
    [applySession],
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
  }, []);

  const refreshMe = useCallback(async () => {
    try {
      const me = await authApi.me();
      setUser(me);
      return me;
    } catch {
      return null;
    }
  }, []);

  const updateUser = useCallback(async (payload: UpdateProfileRequest) => {
    const updated = await usersApi.updateProfile(payload);
    setUser(updated);
    return updated;
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: Boolean(user),
      login,
      register,
      logout,
      refreshMe,
      updateUser,
    }),
    [user, isLoading, login, register, logout, refreshMe, updateUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within <AuthProvider>");
  return context;
}