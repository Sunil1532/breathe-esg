/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        forest: {
          50: '#f0faf0',
          100: '#dcf5dc',
          200: '#bbecbb',
          300: '#85db85',
          400: '#4cc24c',
          500: '#2aa52a',
          600: '#1e851e',
          700: '#1a6b1a',
          800: '#185518',
          900: '#154515',
        },
        slate: {
          850: '#172033',
        }
      }
    },
  },
  plugins: [],
}
