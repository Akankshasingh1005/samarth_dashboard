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
        // Samarth Design System — Teal/Navy palette from logo
        brand: {
          DEFAULT: '#0D7377',
          50: '#E6F5F5',
          100: '#B3E0E1',
          200: '#80CBCD',
          300: '#4DB6B9',
          400: '#1AA1A5',
          500: '#0D7377',
          600: '#0A5C5F',
          700: '#074547',
          800: '#042E2F',
          900: '#021717',
        },
        accent: {
          DEFAULT: '#14919B',
          50: '#E8F6F7',
          100: '#C5E9EB',
          200: '#8DD3D7',
          300: '#56BDC3',
          400: '#14919B',
          500: '#14919B',
          600: '#107780',
          700: '#0C5D64',
        },
        navy: {
          DEFAULT: '#1B3A4B',
          50: '#E8EDF0',
          100: '#C5D0D8',
          200: '#8DA1B0',
          300: '#557289',
          400: '#1B3A4B',
          500: '#1B3A4B',
          600: '#152E3C',
          700: '#10222D',
          800: '#0A161E',
          900: '#050B0F',
        },
        samarth: {
          bg: '#F0F7F7',
          card: '#E2E8F0',
          text: '#1B3A4B',
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
