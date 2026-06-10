/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Modern Natural 色彩系統
        cream: {
          50: '#fdfcfb',   // 最淺奶油白
          100: '#faf9f7',  // 奶油白
          200: '#f5f3f0',  // 米白
          300: '#ebe8e3',  // 淺米灰
          400: '#ddd9d2',  // 米灰
          500: '#c7c2b8',  // 暖灰
        },
        sage: {
          50: '#f6f7f6',   // 極淺鼠尾草
          100: '#e8ebe8',  // 淺鼠尾草
          200: '#d4dbd4',  // 鼠尾草綠
          300: '#a8b5a8',  // 橄欖綠
          400: '#7d8f7d',  // 深鼠尾草
          500: '#5a6d5a',  // 森林綠
        },
        wood: {
          50: '#faf8f5',   // 淺木色
          100: '#f0ebe3',  // 木色
          200: '#e3d9c8',  // 深木色
          300: '#c9b99a',  // 棕木色
          400: '#a08968',  // 深棕
          500: '#7a6a52',  // 咖啡棕
        },
        natural: {
          50: '#fafaf9',   // 自然白
          100: '#f5f5f4',  // 石灰色
          200: '#e7e5e4',  // 淺石色
          300: '#d6d3d1',  // 石色
          400: '#a8a29e',  // 深石色
          500: '#78716c',  // 炭灰
          600: '#57534e',  // 深炭灰
          700: '#44403c',  // 柔和黑
          800: '#292524',  // 深褐黑
        },
        // 保留主色但調整為柔和版本
        primary: {
          50: '#f6f7f6',
          100: '#e8ebe8',
          200: '#d4dbd4',
          300: '#a8b5a8',
          400: '#7d8f7d',
          500: '#5a6d5a',
          600: '#4a5d4a',
          700: '#3a4d3a',
          800: '#2a3d2a',
          900: '#1a2d1a',
        },
      },
      fontFamily: {
        sans: [
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          '"Helvetica Neue"',
          'Arial',
          '"Noto Sans"',
          'sans-serif',
        ],
      },
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1.6', letterSpacing: '0.01em' }],
        'sm': ['0.875rem', { lineHeight: '1.7', letterSpacing: '0.01em' }],
        'base': ['1rem', { lineHeight: '1.75', letterSpacing: '0.01em' }],
        'lg': ['1.125rem', { lineHeight: '1.75', letterSpacing: '0' }],
        'xl': ['1.25rem', { lineHeight: '1.7', letterSpacing: '0' }],
        '2xl': ['1.5rem', { lineHeight: '1.6', letterSpacing: '-0.01em' }],
        '3xl': ['1.875rem', { lineHeight: '1.5', letterSpacing: '-0.01em' }],
        '4xl': ['2.25rem', { lineHeight: '1.4', letterSpacing: '-0.02em' }],
        '5xl': ['3rem', { lineHeight: '1.3', letterSpacing: '-0.02em' }],
        '6xl': ['3.75rem', { lineHeight: '1.2', letterSpacing: '-0.02em' }],
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
      },
      boxShadow: {
        'natural': '0 1px 3px 0 rgba(120, 113, 108, 0.08), 0 1px 2px 0 rgba(120, 113, 108, 0.04)',
        'natural-md': '0 4px 6px -1px rgba(120, 113, 108, 0.08), 0 2px 4px -1px rgba(120, 113, 108, 0.04)',
        'natural-lg': '0 10px 15px -3px rgba(120, 113, 108, 0.08), 0 4px 6px -2px rgba(120, 113, 108, 0.04)',
      },
      animation: {
        'fadeIn': 'fadeIn 0.3s ease-in',
        'fadeOut': 'fadeOut 0.18s ease-out forwards',
        'blink': 'blink 1s step-end infinite',
        'wave': 'wave 3s ease-in-out infinite',
        'wave-slow': 'wave-slow 4s ease-in-out infinite',
        'wave-slower': 'wave-slower 5s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeOut: {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' },
        },
        blink: {
          '0%, 50%': { opacity: '1' },
          '51%, 100%': { opacity: '0' },
        },
        wave: {
          '0%, 100%': {
            transform: 'translateX(0) translateY(0)',
          },
          '25%': {
            transform: 'translateX(-5%) translateY(-3px)',
          },
          '50%': {
            transform: 'translateX(-10%) translateY(0)',
          },
          '75%': {
            transform: 'translateX(-5%) translateY(3px)',
          },
        },
        'wave-slow': {
          '0%, 100%': {
            transform: 'translateX(0) translateY(0)',
          },
          '25%': {
            transform: 'translateX(-7%) translateY(2px)',
          },
          '50%': {
            transform: 'translateX(-14%) translateY(0)',
          },
          '75%': {
            transform: 'translateX(-7%) translateY(-2px)',
          },
        },
        'wave-slower': {
          '0%, 100%': {
            transform: 'translateX(0) translateY(0)',
          },
          '25%': {
            transform: 'translateX(-4%) translateY(-2px)',
          },
          '50%': {
            transform: 'translateX(-8%) translateY(0)',
          },
          '75%': {
            transform: 'translateX(-4%) translateY(2px)',
          },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
