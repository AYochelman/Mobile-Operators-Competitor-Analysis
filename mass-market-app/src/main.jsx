import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { LanguageProvider } from './hooks/useLanguage'
import { AuthProvider } from './hooks/useAuth'
import { WatchlistProvider } from './hooks/useWatchlist'
import { AnnotationCountsProvider } from './hooks/useAnnotationCounts'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <LanguageProvider>
        <AuthProvider>
          <WatchlistProvider>
            <AnnotationCountsProvider>
              <App />
            </AnnotationCountsProvider>
          </WatchlistProvider>
        </AuthProvider>
      </LanguageProvider>
    </BrowserRouter>
  </StrictMode>
)
