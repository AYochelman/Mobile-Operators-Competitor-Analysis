import { defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

const r = (p) => fileURLToPath(new URL(p, import.meta.url))

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
        // Returning visitors carry this SW, whose default navigateFallback serves
        // the precached SPA index.html for ANY navigation - which 404s the static
        // prerendered /esim/<dest>/ pages (no SPA route) and would swallow /go/
        // redirects. Let those hit the network. (/esim-deals starts with "/esim-",
        // not "/esim/", so it deliberately stays on the SPA fallback.)
        navigateFallbackDenylist: [/^\/esim\//, /^\/go\//],
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
        runtimeCaching: [
          {
            urlPattern: /\/api\/(plans|abroad-plans|global-plans|content-plans|changes|abroad-changes|banners|store-banners|global-banners|news)/,
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
      // Two client entries: the SPA (index.html) and a standalone hydration
      // bundle for the prerendered /hotels page. The latter emits
      // dist/assets/hotels-client-*.js, which scripts/prerender-hotels.mjs wires
      // into dist/hotels.html. (entry-hotels.jsx is the SSR sibling, built
      // separately via `vite build --ssr` — it is NOT a client input.)
      input: {
        main: r('./index.html'),
        'hotels-client': r('./src/entry-hotels-client.jsx'),
      },
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
        changeOrigin: true,
        // Flask only serves PNG files under /banners/<file>. The SPA also has
        // a /banners route (Banners tab). Without this bypass, /banners would
        // hit Flask and 404. Only proxy paths that look like image files.
        bypass: (req) => {
          if (!/^\/banners\/[^/?]+\.(png|jpe?g|webp|svg)(\?.*)?$/i.test(req.url)) {
            return req.url
          }
          return null
        }
      },
      '/archive-banners': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})
