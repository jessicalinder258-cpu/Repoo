import { app, BrowserWindow, shell } from 'electron'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const currentDirectory = path.dirname(fileURLToPath(import.meta.url))

const createWindow = () => {
  const window = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 800,
    minHeight: 600,
    backgroundColor: '#f4f1e9',
    title: 'Paperlight PDF Editor',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  window.loadFile(path.join(currentDirectory, '..', 'dist', 'index.html'))

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) void shell.openExternal(url)
    return { action: 'deny' }
  })

  window.webContents.on('will-navigate', (event, url) => {
    if (url !== window.webContents.getURL()) event.preventDefault()
  })
}

app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
