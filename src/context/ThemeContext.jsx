import React, { createContext, useContext, useEffect } from 'react';

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  useEffect(() => {
    // For this hackathon prototype, enforce consistent clean light SaaS theme
    document.documentElement.classList.remove('dark');
    try {
      localStorage.removeItem('devrescue_theme_mode_v2');
      localStorage.removeItem('devrescue_theme_mode');
    } catch {
      // ignore
    }
  }, []);

  return (
    <ThemeContext.Provider value={{ theme: 'light', toggleTheme: () => {}, setMode: () => {}, isDark: false }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
