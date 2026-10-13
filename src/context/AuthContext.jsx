import React, { createContext, useContext, useState } from 'react';

const AuthContext = createContext(null);
const STORAGE_KEY = 'devrescue_demo_auth_user_v2';

const DEFAULT_DEMO_USER = {
  id: 'usr-ansh',
  name: 'Ansh',
  email: 'ansh@devrescue.ai',
  role: 'Lead Engineer',
  avatarUrl: null,
  githubUsername: 'ansh-dev',
  isDemo: true
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  const [loading, setLoading] = useState(false);

  const saveUser = (userData) => {
    setUser(userData);
    try {
      if (userData) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(userData));
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // ignore
    }
  };

  const login = async (email = 'ansh@devrescue.ai', _password = '') => {
    setLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 350));
    const demoUser = {
      ...DEFAULT_DEMO_USER,
      email: email || DEFAULT_DEMO_USER.email,
      name: email.split('@')[0] || 'Ansh'
    };
    saveUser(demoUser);
    setLoading(false);
    return demoUser;
  };

  const register = async (email, _password, name) => {
    setLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 350));
    const demoUser = {
      id: `usr-${Date.now()}`,
      name: name || 'Ansh',
      email: email || 'ansh@devrescue.ai',
      role: 'Software Engineer',
      githubUsername: (name || 'ansh').toLowerCase().replace(/\s+/g, '-'),
      isDemo: true
    };
    saveUser(demoUser);
    setLoading(false);
    return demoUser;
  };

  const loginWithGithub = async () => {
    setLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 300));
    saveUser(DEFAULT_DEMO_USER);
    setLoading(false);
    return DEFAULT_DEMO_USER;
  };

  const loginWithGoogle = async () => {
    setLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 300));
    saveUser(DEFAULT_DEMO_USER);
    setLoading(false);
    return DEFAULT_DEMO_USER;
  };

  const logout = async () => {
    setLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 150));
    saveUser(null);
    setLoading(false);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        loginWithGithub,
        loginWithGoogle,
        logout,
        isDemoMode: true
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
