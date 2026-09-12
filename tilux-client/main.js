const { app, BrowserWindow, ipcMain, Notification } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, exec } = require('child_process');

let pyProc = null;
let mainWindow = null;

function copyDirectory(src, dest) {
    if (!fs.existsSync(dest)) {
        fs.mkdirSync(dest, { recursive: true });
    }
    const entries = fs.readdirSync(src, { withFileTypes: true });
    for (let entry of entries) {
        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);
        if (entry.isDirectory()) {
            copyDirectory(srcPath, destPath);
        } else {
            fs.copyFileSync(srcPath, destPath);
        }
    }
}

async function setupAndRunBackend() {
    if (app.isPackaged) {
        const userDataPath = app.getPath('userData');
        const backendPath = path.join(userDataPath, 'backend');
        const venvPath = path.join(backendPath, 'venv');
        
        let pyExe = process.platform === 'win32' ? 
            path.join(venvPath, 'Scripts', 'python.exe') : 
            path.join(venvPath, 'bin', 'python3');
            
        const setupCompleteFile = path.join(backendPath, '.setup_complete');
        
        // Check if setup is already complete by looking for the .setup_complete flag
        if (!fs.existsSync(setupCompleteFile) || !fs.existsSync(pyExe)) {
            console.log('First launch or broken install detected. Setting up backend...');
            
            // Wipe existing broken venv if it exists
            if (fs.existsSync(venvPath)) {
                fs.rmSync(venvPath, { recursive: true, force: true });
            }
            
            // Show the loading screen
            if (mainWindow) mainWindow.loadFile(path.join(__dirname, 'src', 'loading.html'));
            
            // Wait a moment for UI to render
            await new Promise(r => setTimeout(r, 1000));
            
            if (mainWindow) mainWindow.webContents.send('installation-status', 'Copying AI files to user data...');
            
            // Copy files from resources/backend to userData/backend
            const resourcesBackend = path.join(process.resourcesPath, 'backend');
            if (fs.existsSync(resourcesBackend)) {
                copyDirectory(resourcesBackend, backendPath);
            }
            
            // Create venv and pip install
            await new Promise((resolve, reject) => {
                const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
                if (mainWindow) mainWindow.webContents.send('installation-status', 'Creating virtual environment (this may take a minute)...');
                
                exec(`${pythonCmd} -m venv venv`, { cwd: backendPath }, (err, stdout, stderr) => {
                    if (err) {
                        console.error(err);
                        const errMsg = (stderr || err.message).toLowerCase();
                        let displayMsg = 'Error creating venv: ' + err.message;
                        if (errMsg.includes('venv package') || errMsg.includes('ensurepip')) {
                            displayMsg = 'Missing python3-venv! Open terminal, run "sudo apt install python3-venv", then restart this app.';
                        }
                        if (mainWindow) mainWindow.webContents.send('installation-status', displayMsg);
                        return reject(err);
                    }
                    
                    if (mainWindow) mainWindow.webContents.send('installation-status', 'Installing AI dependencies (this may take 1-3 minutes)...');
                    const pipCmd = process.platform === 'win32' ? 
                        path.join('venv', 'Scripts', 'pip.exe') : path.join('.', 'venv', 'bin', 'pip');
                        
                    exec(`${pipCmd} install -r requirements.txt`, { cwd: backendPath }, (err, stdout, stderr) => {
                        if (err) {
                            console.error(err);
                            if (mainWindow) mainWindow.webContents.send('installation-status', 'Error installing dependencies: ' + err.message);
                            return reject(err);
                        }
                        
                        // Try to install PyAudio optionally (often fails on Linux without portaudio19-dev)
                        if (mainWindow) mainWindow.webContents.send('installation-status', 'Installing optional audio drivers...');
                        exec(`${pipCmd} install PyAudio==0.2.14`, { cwd: backendPath }, (paErr) => {
                            if (paErr) {
                                console.warn('PyAudio optional install failed, voice input may not work:', paErr.message);
                            }
                            // Create flag file to mark successful setup
                            fs.writeFileSync(setupCompleteFile, 'done');
                            resolve();
                        });
                    });
                });
            });
            console.log('Setup complete.');
            if (mainWindow) mainWindow.webContents.send('installation-status', 'Setup complete! Booting AI...');
            await new Promise(r => setTimeout(r, 1000));
        }

        // Run the backend
        const script = path.join(backendPath, 'server.py');
        pyProc = spawn(pyExe, [script], { cwd: backendPath });
        
    } else {
        // Dev mode
        let script = path.join(__dirname, '..', 'server.py');
        const pyExe = process.platform === 'win32' ? 
            path.join(__dirname, '..', 'venv', 'Scripts', 'python.exe') : 
            path.join(__dirname, '..', 'venv', 'bin', 'python3');
        pyProc = spawn(pyExe, [script], { cwd: path.join(__dirname, '..') });
    }

    if (pyProc != null) {
        console.log('Python backend spawned successfully.');
        pyProc.stdout.on('data', (data) => {
            console.log(`Python: ${data.toString()}`);
        });
        pyProc.stderr.on('data', (data) => {
            console.error(`Python Error: ${data.toString()}`);
        });
        
        // Wait 3 seconds for flask to boot then load the real UI
        setTimeout(() => {
            if (mainWindow) {
                mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));
            }
        }, 3000);
    }
}

function exitPythonProcess() {
    if (pyProc) {
        pyProc.kill();
        pyProc = null;
    }
}

function createWindow () {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 900,
        minHeight: 600,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: true, // required for ipcRenderer in loading.html
            contextIsolation: false
        },
        autoHideMenuBar: true,
        title: "Tilux Assistant",
        icon: path.join(__dirname, 'src', 'icon.png')
    });
    
    // Set a blank background while loading
    mainWindow.loadFile(path.join(__dirname, 'src', 'loading.html'));
}

app.whenReady().then(async () => {
    createWindow();
    
    try {
        await setupAndRunBackend();
    } catch (e) {
        console.error("Backend setup failed:", e);
    }

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('will-quit', () => {
    exitPythonProcess();
});

ipcMain.on('show-notification', (event, text) => {
    if (Notification.isSupported()) {
        const notif = new Notification({
            title: 'Tilux',
            body: text,
            icon: path.join(__dirname, 'templates', 'app.png')
        });
        notif.on('click', () => {
            if (mainWindow) {
                if (mainWindow.isMinimized()) mainWindow.restore();
                mainWindow.focus();
            }
        });
        notif.show();
    }
});
