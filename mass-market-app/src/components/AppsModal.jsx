import Modal from './ui/Modal'

export default function AppsModal({ open, onClose, title, apps }) {
  if (!apps) return null
  return (
    <Modal open={open} onClose={onClose} title={title} maxWidth="max-w-md">
      {/* Names only: the app logos used to be hot-linked from Wikimedia (third-party
          trademarks + a hotlinking-policy violation); a text chip carries the same
          information and is announced correctly by screen readers. */}
      <div className="flex flex-wrap gap-2 justify-center">
        {apps.map(app => (
          <span key={app.name} className="inline-flex items-center rounded-full border border-moca-border bg-white px-3 py-1.5 text-sm font-semibold text-moca-dark">
            {app.name}
          </span>
        ))}
      </div>
    </Modal>
  )
}
