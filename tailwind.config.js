/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#FFFFFF',
        secondary: '#F7F9FC',
        card: '#FFFFFF',
        'text-primary': '#0F172A',
        'text-secondary': '#64748B',
        'brand-blue': '#2563EB',
        'brand-dark': '#1E3A8A',
        'brand-hover': '#1D4ED8',
        'brand-light': '#EFF6FF',
        'border-ui': '#E2E8F0',
        'status-success': '#16A34A',
        'status-warning': '#D97706',
        'status-error': '#DC2626',
        'code-editor': '#0F172A',

        // Legacy compatibility aliases
        paper: '#FFFFFF',
        'paper-deep': '#F7F9FC',
        surface: '#FFFFFF',
        'surface-elevated': '#F7F9FC',
        'surface-card': '#FFFFFF',
        'border-dim': '#E2E8F0',
        'border-bright': '#CBD5E1',
        ink: '#0F172A',
        'ink-soft': '#64748B',
        'ink-faint': '#94A3B8',
        accent: '#2563EB',
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'subtle': '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px 0 rgba(0, 0, 0, 0.03)',
        'card': '0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.04)',
        'card-hover': '0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.04)',
        'modal': '0 20px 25px -5px rgba(15, 23, 42, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.06)',
      },
      animation: {
        'pulse-subtle': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
