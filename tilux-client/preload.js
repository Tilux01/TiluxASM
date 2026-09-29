const { ipcRenderer } = require('electron');

window.electronAPI = {
    showNotification: (text) => ipcRenderer.send('show-notification', text)
};
