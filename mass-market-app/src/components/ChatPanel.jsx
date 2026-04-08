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
  'esimio': { id: 'esimio', tab: 'global' },
  'esim.io': { id: 'esimio', tab: 'global' },
  'Sparks': { id: 'sparks', tab: 'global' },
  'sparks': { id: 'sparks', tab: 'global' },
  'VOYE': { id: 'voye', tab: 'global' },
  'voye': { id: 'voye', tab: 'global' },
  'Voye': { id: 'voye', tab: 'global' },
  'airalo': { id: 'airalo', tab: 'global' },
  'saily': { id: 'saily', tab: 'global' },
  'holafly': { id: 'holafly', tab: 'global' },
  'tuki': { id: 'tuki', tab: 'global' },
}

// Build regex from carrier names (longest first to avoid partial matches)
const CARRIER_REGEX = new RegExp(
  '(' + Object.keys(CARRIER_MAP).sort((a, b) => b.length - a.length).map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')',
  'g'
)

function renderMessageWithLinks(text, onCarrierClick) {
  const parts = text.split(CARRIER_REGEX)
  return parts.map((part, i) => {
    const carrier = CARRIER_MAP[part]
    if (carrier) {
      return (
        <button
          key={i}
          onClick={() => onCarrierClick(carrier, text)}
          className="text-moca-bolt hover:text-moca-dark underline underline-offset-2 font-medium cursor-pointer"
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

  const handleCarrierClick = (carrier, contextText) => {
    const params = new URLSearchParams()
    params.set('tab', carrier.tab)
    params.set('carrier', carrier.id)
    // Extract plan name near the clicked carrier for highlighting
    // The AI formats plans like: "carrier | PLAN_NAME" or "**carrier PLAN_NAME**"
    let highlight = carrier.id
    if (contextText) {
      // Try to find a line with the carrier name + plan details
      const lines = contextText.split('\n')
      for (const line of lines) {
        if (line.includes(carrier.id) || Object.keys(CARRIER_MAP).some(k => CARRIER_MAP[k].id === carrier.id && line.includes(k))) {
          // Extract plan name pattern (contains GB or has dashes)
          const planMatch = line.match(/[\u0590-\u05FF\w][\u0590-\u05FF\w\s\-–]+\d+\s*GB/i)
            || line.match(/\|[\s]*([^\|]+\d+\s*GB[^\|]*)/i)
            || line.match(/\*\*([^*]+)\*\*/i)
          if (planMatch) {
            highlight = (planMatch[1] || planMatch[0]).replace(/\*\*/g, '').trim()
            break
          }
        }
      }
    }
    params.set('highlight', highlight)
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
        className="fixed bottom-5 left-5 z-50 px-4 h-10 rounded-full bg-moca-bolt text-white shadow-lg hover:bg-moca-dark transition-all flex items-center justify-center text-xs font-semibold tracking-wide"
      >
        {open ? '✕' : 'Ask AI'}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-20 left-5 z-50 w-[340px] max-w-[calc(100vw-40px)] bg-white rounded-xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden animate-fade-in-up" style={{ maxHeight: '70vh' }}>
          {/* Header */}
          <div className="bg-moca-bolt text-white px-4 py-3 flex items-center justify-between flex-shrink-0">
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
                      className="text-[11px] px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-full text-gray-600 hover:bg-moca-cream hover:border-moca-border hover:text-moca-bolt transition-colors"
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
                    ? 'bg-moca-cream text-moca-text'
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
              className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-moca-bolt focus:border-moca-bolt max-h-[80px]"
              style={{ fontSize: '16px' }}
            />
            <button
              onClick={() => sendMessage()}
              disabled={loading || !input.trim()}
              className="px-3 py-2 bg-moca-bolt text-white rounded-lg text-sm font-medium hover:bg-moca-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
            >
              שלח
            </button>
          </div>
        </div>
      )}
    </>
  )
}
