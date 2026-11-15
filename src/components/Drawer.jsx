// Detail panel: a bottom sheet above every other control (timeline included) on phones, a floating card on desktop.
// Closing is the card's own close button; the sheet has no other state.
export default function Drawer({ label, children }) {
  return (
    <aside aria-label={label} className="pointer-events-auto fixed inset-x-0 bottom-0 z-30 flex max-h-[55dvh] flex-col overflow-hidden rounded-t-2xl bg-chalk shadow-float md:absolute md:inset-x-auto md:bottom-auto md:right-3 md:top-[5rem] md:z-10 md:max-h-[calc(100%-6.5rem)] md:w-[22rem] md:rounded-2xl">
      {children}
    </aside>
  )
}
