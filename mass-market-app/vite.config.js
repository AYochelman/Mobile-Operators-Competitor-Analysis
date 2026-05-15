import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icons/*.png', 'logos/*.png'],
      manifest: false, // public/manifest.json is served manually
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg}'],
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
        runtimeCaching: [
          {
            urlPattern: /\/api\/(plans|abroad-plans|global-plans|content-plans|changes|abroad-changes|banners|store-banners|news)/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'api-data-cache',
              expiration: { maxEntries: 50, maxAgeSeconds: 43200 },
              cacheableResponse: { statuses: [0, 200] }
            }
          },
          {
            urlPattern: /\/(banners|logos|icons)\//,
            handler: 'CacheFirst',
            options: {
              cacheName: 'static-assets-cache',
              expiration: { maxEntries: 100, maxAgeSeconds: 604800 },
              cacheableResponse: { statuses: [0, 200] }
            }
          }
        ]
      }
    })
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/') || id.includes('node_modules/react-router')) {
            return 'vendor-react'
          }
          if (id.includes('node_modules/@supabase/')) {
            return 'vendor-supabase'
          }
        },
      },
    },
  },
  server: {
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/banners': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/archive-banners': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})
