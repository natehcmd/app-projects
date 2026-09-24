/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/ui/index.html', './src/ui/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        // Terminal-matched palette so the dashboard and cmux feel like one tool.
        conductor: {
          bg: '#0b0f19',
          panel: '#0f172a',
          border: '#1e293b',
        },
      },
      keyframes: {
        'pulse-ring': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(239, 68, 68, 0.45)' },
          '50%': { boxShadow: '0 0 0 6px rgba(239, 68, 68, 0)' },
        },
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.8s ease-out infinite',
      },
    },
  },
  plugins: [],
};
