import { Link } from 'react-router-dom'
import Button from '../components/ui/Button'

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <p className="text-6xl mb-4">🔍</p>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">העמוד לא נמצא</h1>
        <p className="text-gray-500 mb-6">404</p>
        <Link to="/"><Button>חזרה לדשבורד</Button></Link>
      </div>
    </div>
  )
}
