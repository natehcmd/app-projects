import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import * as path from 'node:path';

// The Control Tower is a standalone SPA served by Vite in dev. It talks to the
// daemon purely over the WebSocket at CONDUCTOR_WS_* — there is no HTTP proxy
// to configure.
export default defineConfig({
  root: path.resolve(__dirname, 'src/ui'),
  plugins: [react()],
  server: {
    port: 5273,
    strictPort: false,
  },
  build: {
    outDir: path.resolve(__dirname, 'dist/ui'),
    emptyOutDir: true,
  },
});
