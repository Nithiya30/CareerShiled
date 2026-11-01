/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        shield: {
          bg: 'rgb(var(--shield-bg) / <alpha-value>)',
          surface: 'rgb(var(--shield-surface) / <alpha-value>)',
          card: 'rgb(var(--shield-card) / <alpha-value>)',
          cardHover: 'rgb(var(--shield-card-hover) / <alpha-value>)',
          border: 'rgb(var(--shield-border) / <alpha-value>)',
          borderLight: 'rgb(var(--shield-border-light) / <alpha-value>)',
          accent: '#06B6D4',
          accentHover: '#0891B2',
          cyan: '#00E5FF',
          blue: '#3B82F6',
          legit: '#10B981',
          uncertain: '#F59E0B',
          fraud: '#EF4444',
          muted: 'rgb(var(--shield-muted) / <alpha-value>)',
          text: 'rgb(var(--shield-text) / <alpha-value>)',
          textMuted: 'rgb(var(--shield-text-muted) / <alpha-value>)'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace']
      }
    },
  },
  plugins: [],
}
