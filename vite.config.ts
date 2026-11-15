import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Static output only. `base: './'` keeps the build portable (e.g. a GitHub Pages sub-path).
export default defineConfig({
  base: './',
  plugins: [react()],
});
