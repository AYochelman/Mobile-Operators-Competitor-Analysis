import Modal from './ui/Modal'

export default function AppsModal({ open, onClose, title, apps }) {
  if (!apps) return null
  return (
    <Modal open={open} onClose={onClose} title={`📱 ${title}`} maxWidth="max-w-md">
      <div className="flex flex-wrap gap-3 justify-center">
        {apps.map(app => (
          <div key={app.name} className="flex flex-col items-center gap-1.5 w-14">
            <div className="w-11 h-11 rounded-xl bg-white border border-gray-100 shadow-sm flex items-center justify-center p-1.5">
              <img
                src={app.logo}
                alt={app.name}
                className="w-full h-full object-contain"
                onError={e => { e.target.style.display = 'none' }}
              />
            </div>
            <span className="text-[10px] text-gray-500 text-center leading-tight">{app.name}</span>
          </div>
        ))}
      </div>
    </Modal>
  )
}
