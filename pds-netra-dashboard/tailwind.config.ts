import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        border: 'hsl(214 32% 91%)',
        foreground: 'hsl(222.2 84% 4.9%)'
      }
    }
  },
  plugins: []
};

export default config;
