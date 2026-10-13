/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        display: ["Space Grotesk", "Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        // Dark-first surfaces
        ink: {
          950: "#050508",
          900: "#09090e",
          850: "#0c0c12",
          800: "#101018",
          700: "#16161f",
          600: "#1d1d29",
          500: "#262634",
          400: "#34344a",
        },
        // Purple brand
        brand: {
          50: "#f5f3ff",
          100: "#ede9fe",
          200: "#ddd6fe",
          300: "#c4b5fd",
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
          700: "#6d28d9",
          800: "#5b21b6",
          900: "#4c1d95",
        },
        // Electric blue accent
        accent: {
          50: "#ecfeff",
          100: "#cffafe",
          200: "#a5f3fc",
          300: "#67e8f9",
          400: "#22d3ee",
          500: "#06b6d4",
          600: "#0891b2",
          700: "#0e7490",
          800: "#155e75",
          900: "#164e63",
        },
      },
      opacity: {
        8: "0.08",
        12: "0.12",
      },
      boxShadow: {
        glow: "0 0 24px -6px rgba(139, 92, 246, 0.55)",
        "glow-lg": "0 0 48px -8px rgba(139, 92, 246, 0.6)",
        "glow-blue": "0 0 24px -6px rgba(34, 211, 238, 0.55)",
        "glow-inset": "inset 0 1px 0 0 rgba(255,255,255,0.06)",
        "card": "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 12px 32px -12px rgba(0,0,0,0.6)",
        "card-hover": "0 1px 0 0 rgba(255,255,255,0.06) inset, 0 20px 48px -16px rgba(0,0,0,0.75), 0 0 32px -12px rgba(139, 92, 246, 0.35)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #7c3aed 0%, #6d28d9 45%, #22d3ee 130%)",
        "brand-gradient-soft": "linear-gradient(135deg, rgba(124,58,237,0.18), rgba(34,211,238,0.10))",
        "aurora": "radial-gradient(60% 50% at 20% 0%, rgba(124,58,237,0.22), transparent 60%), radial-gradient(50% 40% at 90% 10%, rgba(34,211,238,0.16), transparent 60%), radial-gradient(70% 60% at 50% 100%, rgba(109,40,217,0.10), transparent 70%)",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
        "fade-in-slow": "fadeIn 0.6s ease-out",
        "slide-up": "slideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1)",
        "scale-in": "scaleIn 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
        shimmer: "shimmer 1.6s infinite linear",
        float: "float 6s ease-in-out infinite",
        "pulse-glow": "pulseGlow 3s ease-in-out infinite",
        "spin-slow": "spin 14s linear infinite",
        "orbit": "orbit 22s linear infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        scaleIn: {
          "0%": { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-12px)" },
        },
        pulseGlow: {
          "0%, 100%": { opacity: "0.55", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.06)" },
        },
        orbit: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
      },
    },
  },
  plugins: [],
};
