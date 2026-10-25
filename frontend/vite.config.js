import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // Ports locaux dédiés au projet (8000/5173 étaient pris par d'autres
    // projets de la machine) : 5190 pour le frontend, 8110 pour l'API.
    port: 5190,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8110',
        changeOrigin: true,
      },
      // Documentation OpenAPI servie par le backend en développement.
      '/docs': {
        target: 'http://localhost:8110',
        changeOrigin: true,
      },
      '/openapi.json': {
        target: 'http://localhost:8110',
        changeOrigin: true,
      },
    },
  },
});
