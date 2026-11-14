const { ipcRenderer } = require('electron');

window.electronAPI = {
    platform: process.platform,
    showNotification: (text) => ipcRenderer.send('show-notification', text),
    showWakePopup: () => ipcRenderer.send('show-wake-popup'),
    hideWakePopup: () => ipcRenderer.send('hide-wake-popup'),
    openChatWithPrompt: (prompt) => ipcRenderer.send('open-chat-with-prompt', prompt),
    restartAppAndServer: () => ipcRenderer.send('restart-app-and-server'),
    minimizeWindow: () => ipcRenderer.send('window-minimize'),
    maximizeWindow: () => ipcRenderer.send('window-maximize'),
    closeWindow: () => ipcRenderer.send('window-close')
};
