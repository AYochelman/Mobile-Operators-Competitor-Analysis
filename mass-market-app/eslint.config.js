import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  // Build outputs (SPA bundle + the two SSR prerender bundles) are never linted.
  globalIgnores(['dist', 'dist-ssr', 'dist-ssr-hotels']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
      // `try { localStorage... } catch {}` guards are the house pattern for
      // storage access that may throw (private mode, blocked site data).
      'no-empty': ['error', { allowEmptyCatch: true }],
      // React Compiler adoption rules (shipped in eslint-plugin-react-hooks 6).
      // The app does not use the compiler; these stay advisory (warn) until the
      // flagged effects are reworked. rules-of-hooks / exhaustive-deps keep their defaults.
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/purity': 'warn',
      'react-hooks/error-boundaries': 'warn',
      'react-hooks/immutability': 'warn',
      'react-hooks/refs': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
      'react-hooks/use-memo': 'warn',
      'react-hooks/static-components': 'warn',
      'react-hooks/globals': 'warn',
    },
  },
  {
    // Context hooks deliberately export both the Provider component and the
    // hook from one file; Fast Refresh falls back to a full reload for them.
    files: ['src/hooks/**/*.jsx', 'src/components/LogoField.jsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
  {
    // Web-push service worker (imported into the Workbox SW via importScripts).
    files: ['public/push-sw.js'],
    languageOptions: { globals: { ...globals.serviceworker, ...globals.browser } },
  },
])
