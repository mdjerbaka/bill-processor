import { useState, useEffect, useCallback } from 'react'

export default function ContextMenu({ items }) {
  const [visible, setVisible] = useState(false)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [targetData, setTargetData] = useState(null)

  const hide = useCallback(() => setVisible(false), [])

  useEffect(() => {
    if (visible) {
      const handler = () => hide()
      document.addEventListener('click', handler)
      document.addEventListener('contextmenu', handler)
      return () => {
        document.removeEventListener('click', handler)
        document.removeEventListener('contextmenu', handler)
      }
    }
  }, [visible, hide])

  function show(e, data) {
    e.preventDefault()
    e.stopPropagation()
    setTargetData(data)
    setPosition({ x: e.clientX, y: e.clientY })
    setVisible(true)
  }

  const menu = visible ? (
    <div
      className="fixed z-50 bg-gray-800 border border-gray-600 rounded-lg shadow-xl py-1 min-w-[160px]"
      style={{ top: position.y, left: position.x }}
      onClick={(e) => e.stopPropagation()}
    >
      {items.map((item, i) => (
        <button
          key={i}
          onClick={() => { item.onClick(targetData); hide() }}
          className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-700 transition-colors flex items-center gap-2 ${
            item.danger ? 'text-red-400 hover:text-red-300' : 'text-gray-200'
          }`}
        >
          {item.icon && <item.icon className="h-4 w-4" />}
          {item.label}
        </button>
      ))}
    </div>
  ) : null

  return { show, menu }
}
