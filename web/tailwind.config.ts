import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        solar:           '#e4f222',
        'solar-light':   '#f5ff78',
        'gray-light':    '#f4f2f0',
        'gray-medium':   '#d2cecb',
        'gray-dark':     '#6e6a68',
        'vault-black':   '#1a1919',
        'text-primary':  '#0c0a08',
        smolder:         '#17332d',
        blaze:           '#e96516',
        spring:          '#5683d2',
        // keep old tokens so existing code doesn't break
        vault: { ink: '#0c0a08', paper: '#f4f2f0', accent: '#e4f222' },
      },
      fontFamily: {
        sans: ['Geist', 'Inter', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '6px',
      },
    },
  },
  plugins: [],
} satisfies Config;
