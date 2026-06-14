export async function openDB() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open("FlashcardDB", 1)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains("files")) {
        db.createObjectStore("files")
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export async function saveFile(id: string, data: Blob | string) {
  const db = await openDB()
  return new Promise<void>((resolve, reject) => {
    const tx = db.transaction("files", "readwrite")
    const store = tx.objectStore("files")
    const request = store.put(data, id)
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
  })
}

export async function getFile(id: string): Promise<Blob | string | null> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction("files", "readonly")
    const store = tx.objectStore("files")
    const request = store.get(id)
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export async function deleteFile(id: string) {
  const db = await openDB()
  return new Promise<void>((resolve, reject) => {
    const tx = db.transaction("files", "readwrite")
    const store = tx.objectStore("files")
    const request = store.delete(id)
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
  })
}
