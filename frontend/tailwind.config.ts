/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Samarth Design System - Teal/Navy palette from logo
        brand: {
          DEFAULT: '#229096',
          50: '#E9F7F8',
          100: '#C8EAEC',
          200: '#93D4D8',
          300: '#5DBFC3',
          400: '#2FA5AA',
          500: '#229096',
          600: '#1B7478',
          700: '#15575A',
          800: '#0E3A3C',
          900: '#071D1E',
        },
        accent: {
          DEFAULT: '#2A5BC4',
          50: '#EAF0FB',
          100: '#CAD8F3',
          200: '#95B1E8',
          300: '#608ADD',
          400: '#3E70D1',
          500: '#2A5BC4',
          600: '#22499D',
          700: '#193776',
        },
        navy: {
          DEFAULT: '#0F172A',
          50: '#E2E8F0',
          100: '#CBD5E1',
          200: '#94A3B8',
          300: '#64748B',
          400: '#334155',
          500: '#0F172A',
          600: '#0C1222',
          700: '#090E19',
          800: '#060912',
          900: '#030509',
        },
        samarth: {
          bg: '#F8FAFC',
          card: '#E2E8F0',
          text: '#0F172A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.4s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'skeleton': 'skeleton 1.5s ease-in-out infinite',
        'alert-pulse': 'alertPulse 1.5s ease-in-out infinite',
        'slide-in-right': 'slideInRight 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        skeleton: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        alertPulse: {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 0 0 rgba(239, 68, 68, 0.4)' },
          '50%': { opacity: '0.9', boxShadow: '0 0 0 8px rgba(239, 68, 68, 0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [],
}
