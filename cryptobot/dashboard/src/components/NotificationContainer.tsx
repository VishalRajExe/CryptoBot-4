import { useStore } from '@/store'
import { cn } from '@/lib/utils'

export function NotificationContainer() {
  const { notifications, removeNotification } = useStore()

  if (notifications.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {notifications.map((notification) => (
        <Notification
          key={notification.id}
          notification={notification}
          onClose={() => removeNotification(notification.id)}
        />
      ))}
    </div>
  )
}

function Notification({ notification, onClose }: { notification: any; onClose: () => void }) {
  const icons = {
    success: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
    error: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    warning: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
    info: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  }

  const colors = {
    success: 'bg-success-500/10 border-success-500/20 text-success-500',
    error: 'bg-danger-500/10 border-danger-500/20 text-danger-500',
    warning: 'bg-yellow-500/10 border-yellow-500/20 text-yellow-500',
    info: 'bg-primary-500/10 border-primary-500/20 text-primary-500',
  }

  return (
    <div
      className={cn(
        'flex items-start gap-3 p-4 rounded-xl border shadow-lg min-w-[300px] max-w-md',
        'animate-slide-in',
        colors[notification.type]
      )}
      role="alert"
    >
      <div className="flex-shrink-0 mt-0.5">
        {icons[notification.type]}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{notification.message}</p>
      </div>
      <button
        onClick={onClose}
        className="flex-shrink-0 p-1 rounded-lg hover:bg-black/10 transition-colors"
        aria-label="Dismiss"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}