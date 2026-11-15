// Holds at most one async resource (the focused municipality's water mesh, its trees). Setting a new key removes the
// previous resource first, then builds the next; keys that change again while a build is in flight are skipped.
// A resource is { remove() }; build(key) may resolve null (nothing to show, or the map went away).
export function createSlot(build) {
  let key = null
  let current = Promise.resolve(null)
  return {
    get key() {
      return key
    },
    get ready() {
      return current
    },
    set(next) {
      if (next === key) return current
      key = next
      const prev = current
      current = prev
        .catch(() => null)
        .then((old) => old?.remove())
        .then(() => (next === key && next != null ? build(next) : null))
        .catch((e) => {
          console.error(e)
          return null
        })
      return current
    },
  }
}
