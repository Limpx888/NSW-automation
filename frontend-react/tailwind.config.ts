import type { Config } from 'tailwindcss'

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Industrial Slate/Dark Navy
        'industrial': {
          'bg': '#0B0F17',
          'card': '#161C28',
          'border': '#2A3340',
          'text': '#E5E7EB',
          'text-muted': '#9CA3AF',
        },
        // Status Semantic Colors
        'status': {
          'healthy': '#10B981',
          'attention': '#F59E0B',
          'critical': '#EF4444',
          'highlight': '#6366F1',
        },
      },
      fontFamily: {
        'mono': ['"JetBrains Mono"', '"Roboto Mono"', 'monospace'],
      },
      animation: {
        'pulse-beacon': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.3s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(-100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
} satisfies Config
