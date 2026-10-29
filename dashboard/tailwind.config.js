/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f4ff',
          100: '#e0e9ff',
          200: '#c7d6fe',
          300: '#a3b8fd',
          400: '#7a8ffc',
          500: '#5c6ffb',
          600: '#4855e8',
          700: '#3d42c7',
          800: '#36389f',
          900: '#31347f',
        },
        dark: {
          bg: '#0f1117',
          card: '#161a22',
          border: '#2a2f3e',
          text: '#e4e6eb',
          muted: '#8b91a0',
        },
        success: {
          500: '#10b981',
          600: '#059669',
        },
        danger: {
          500: '#ef4444',
          600: '#dc2626',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 2s linear infinite',
      },
    },
  },
  plugins: [],
  darkMode: 'class',
}