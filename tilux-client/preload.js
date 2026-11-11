const { ipcRenderer } = require('electron');

window.electronAPI = {
    showNotification: (text) => ipcRenderer.send('show-notification', text),
    showWakePopup: () => ipcRenderer.send('show-wake-popup'),
    hideWakePopup: () => ipcRenderer.send('hide-wake-popup'),
    openChatWithPrompt: (prompt) => ipcRenderer.send('open-chat-with-prompt', prompt)
};
