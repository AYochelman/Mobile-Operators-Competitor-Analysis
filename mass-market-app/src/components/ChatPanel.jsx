import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

const EXAMPLES = [
  'מה החבילה הכי זולה עם 5G?',
  'השוו בין פרטנר לפלאפון',
  'איזה eSIM הכי משתלם לאירופה?',
  'מה השתנה היום?',
]

// Map carrier names (Hebrew + English) to their IDs and tabs
const CARRIER_MAP = {
  'פרטנר': { id: 'partner', tab: 'domestic' },
  'פלאפון': { id: 'pelephone', tab: 'domestic' },
  'הוט מובייל': { id: 'hotmobile', tab: 'domestic' },
  'סלקום': { id: 'cellcom', tab: 'domestic' },
  '019': { id: 'mobile019', tab: 'domestic' },
  'xphone': { id: 'xphone', tab: 'domestic' },
  'XPhone': { id: 'xphone', tab: 'domestic' },
  'we-com': { id: 'wecom', tab: 'domestic' },
  'We-Com': { id: 'wecom', tab: 'domestic' },
  'Tuki': { id: 'tuki', tab: 'global' },
  'GlobaleSIM': { id: 'globalesim', tab: 'global' },
  'Airalo': { id: 'airalo', tab: 'global' },
  'GlobalSIM': { id: 'pelephone_global', tab: 'global' },
  'eSIMo': { id: 'esimo', tab: 'global' },
  'SimTLV': { id: 'simtlv', tab: 'global' },
  '8 World': { id: 'world8', tab: 'global' },
  'XPhone Global': { id: 'xphone_global', tab: 'global' },
  'Saily': { id: 'saily', tab: 'global' },
  'Holafly': { id: 'holafly', tab: 'global' },
  'eSIM.io': { id: 'esimio', tab: 'global' },
  'Sparks': { id: 'sparks', tab: 'global' },
  'VOYE': { id: 'voye', tab: 'global' },
}

// Build regex from carrier names (longest first to avoid partial matches)
const CARRIER_REGEX = new RegExp(
  '(' + Object.keys(CARRIER_MAP).sort((a, b) => b.length - a.length).map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')',
  'g'
)

function renderMessageWithLinks(text, onCarrierClick) {
  // Split text by carrier names and make them clickable
  const parts = text.split(CARRIER_REGEX)
  return parts.map((part, i) => {
    const carrier = CARRIER_MAP[part]
    if (carrier) {
      return (
        <button
          key={i}
          onClick={() => onCarrierClick(carrier)}
          className="text-blue-600 hover:text-blue-800 underline underline-offset-2 font-medium cursor-pointer"
        >
          {part}
        </button>
      )
    }
    return <span key={i}>{part}</span>
  })
}

export default function ChatPanel() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEnd = useRef(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus()
  }, [open])

  const handleCarrierClick = (carrier) => {
    // Navigate to dashboard with the carrier pre-selected
    // Use URL params to pass filter state
    const params = new URLSearchParams()
    params.set('tab', carrier.tab)
    params.set('carrier', carrier.id)
    navigate(`/?${params.toString()}`)
    setOpen(false)
  }

  const sendMessage = async (text) => {
    const q = (text || input).trim()
    if (!q || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: q }])
    setLoading(true)
    try {
      const res = await api.chat(q)
      setMessages(prev => [...prev, { role: 'assistant', text: res.answer || 'לא התקבלה תשובה' }])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', text: `❌ ${err.message}` }])
    }
    setLoading(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <>
      {/* FAB button */}
      <button
        onClick={() => setOpen(!open)}
        className="fixed bottom-5 left-5 z-50 px-4 h-10 rounded-full bg-gray-900 text-white shadow-lg hover:bg-gray-800 transition-all flex items-center justify-center text-xs font-semibold tracking-wide"
      >
        {open ? '✕' : 'Ask AI'}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-20 left-5 z-50 w-[340px] max-w-[calc(100vw-40px)] bg-white rounded-xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden animate-fade-in-up" style={{ maxHeight: '70vh' }}>
          {/* Header */}
          <div className="bg-blue-600 text-white px-4 py-3 flex items-center justify-between flex-shrink-0">
            <h3 className="text-sm font-bold">💬 צריך עזרה?</h3>
            <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white text-lg leading-none">&times;</button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-[200px]">
            {messages.length === 0 && (
              <div className="text-center py-4">
                <p className="text-xs text-gray-400 mb-3">שאל אותי על חבילות סלולר</p>
                <div className="flex flex-wrap gap-1.5 justify-center">
                  {EXAMPLES.map((ex, i) => (
                    <button
                      key={i}
                      onClick={() => sendMessage(ex)}
                      className="text-[11px] px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-full text-gray-600 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-600 transition-colors"
                    >
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-start' : 'justify-end'}`}>
                <div className={`max-w-[85%] px-3 py-2 rounded-lg text-sm whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-blue-50 text-gray-800'
                    : 'bg-gray-100 text-gray-700'
                }`}>
                  {msg.role === 'assistant'
                    ? renderMessageWithLinks(msg.text, handleCarrierClick)
                    : msg.text
                  }
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-end">
                <div className="bg-gray-100 px-3 py-2 rounded-lg text-sm text-gray-400">⏳ מחשב...</div>
              </div>
            )}
            <div ref={messagesEnd} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 p-2 flex gap-2 flex-shrink-0">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="שאל שאלה..."
              rows={1}
              className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 max-h-[80px]"
              style={{ fontSize: '16px' }}
            />
            <button
              onClick={() => sendMessage()}
              disabled={loading || !input.trim()}
              className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
            >
              שלח
            </button>
          </div>
        </div>
      )}
    </>
  )
}
