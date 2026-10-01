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
    let script, pyExe, backendCwd;

    if (app.isPackaged) {
        const userDataPath = app.getPath('userData');
        backendCwd = path.join(userDataPath, 'backend');
        
        const venvPath = path.join(backendCwd, 'venv');
        
        pyExe = process.platform === 'win32' ? 
            path.join(venvPath, 'Scripts', 'python.exe') : 
            path.join(venvPath, 'bin', 'python3');
            
        script = path.join(backendCwd, 'server.py');
        const setupCompleteFile = path.join(backendCwd, '.setup_complete');
        
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
                copyDirectory(resourcesBackend, backendCwd);
            }
            
            // Create venv and pip install
            await new Promise((resolve, reject) => {
                const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
                if (mainWindow) mainWindow.webContents.send('installation-status', 'Creating virtual environment (this may take a minute)...');
                
                function runSpawn(cmd, args, cwdStr) {
                    return new Promise((res, rej) => {
                        const child = spawn(cmd, args, { cwd: cwdStr, shell: true });
                        child.stdout.on('data', data => {
                            const lines = data.toString().split('\n').map(l => l.trim()).filter(l => l);
                            if (mainWindow && lines.length > 0) {
                                mainWindow.webContents.send('installation-status', lines[lines.length - 1]);
                            }
                        });
                        child.stderr.on('data', data => {
                            const lines = data.toString().split('\n').map(l => l.trim()).filter(l => l);
                            if (mainWindow && lines.length > 0) {
                                mainWindow.webContents.send('installation-status', lines[lines.length - 1]);
                            }
                        });
                        child.on('close', code => {
                            if (code === 0) res();
                            else rej(new Error(`${cmd} exited with code ${code}`));
                        });
                        child.on('error', err => rej(err));
                    });
                }
                
                runSpawn(pythonCmd, ['-m', 'venv', 'venv'], backendCwd)
                    .then(() => {
                        const pyCmd = process.platform === 'win32' ? path.join('venv', 'Scripts', 'python.exe') : path.join('.', 'venv', 'bin', 'python3');
                        if (mainWindow) mainWindow.webContents.send('installation-status', 'Running system setup (FFmpeg, OCR, Dependencies)...');
                        return runSpawn(pyCmd, ['install.py'], backendCwd);
                    })
                    .then(() => {
                        fs.writeFileSync(setupCompleteFile, 'done');
                        resolve();
                    })
                    .catch(err => {
                        console.error(err);
                        if (mainWindow) mainWindow.webContents.send('installation-status', 'Installation Error: ' + err.message);
                        reject(err);
                    });
            });
            console.log('Setup complete.');
            if (mainWindow) mainWindow.webContents.send('installation-status', 'Setup complete! Booting AI...');
            await new Promise(r => setTimeout(r, 1000));
        }
    } else {
        // Dev mode
        backendCwd = path.join(__dirname, '..');
        script = path.join(backendCwd, 'server.py');
        pyExe = process.platform === 'win32' ? 
            path.join(backendCwd, 'venv', 'Scripts', 'python.exe') : 
            path.join(backendCwd, 'venv', 'bin', 'python3');
    }
    
    const http = require('http');
    const checkBackendRunning = () => {
        return new Promise((resolve) => {
            const req = http.get('http://127.0.0.1:8932/api/host_info', (res) => {
                resolve(res.statusCode === 200);
            });
            req.on('error', () => resolve(false));
            req.setTimeout(800, () => {
                req.destroy();
                resolve(false);
            });
        });
    };

    const isRunning = await checkBackendRunning();
    if (!isRunning) {
        const spawnArgs = script ? [script] : [];
        pyProc = spawn(pyExe, spawnArgs, { cwd: backendCwd });
        console.log('Python backend spawned successfully.');
        pyProc.stdout.on('data', (data) => {
            console.log(`Python: ${data.toString()}`);
        });
        pyProc.stderr.on('data', (data) => {
            console.error(`Python Error: ${data.toString()}`);
        });
    } else {
        console.log('Python backend is already running on port 8932. Reusing active process.');
    }

    // Clean & snappy splash transition (1.4 seconds)
    setTimeout(() => {
        if (mainWindow) {
            mainWindow.webContents.session.clearCache().then(() => {
                mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));
            });
        }
    }, 1400);
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
    const isWidgetMode = process.argv.includes('--widget');
    if (isWidgetMode) {
        // We still need to call the IPC handler logic we defined below, so we just trigger it internally
        // But the IPC handler doesn't exist until the event is fired, so let's extract the wake window logic
        createWakeWindow();
    } else {
        createWindow();
    }
    
    try {
        await setupAndRunBackend();
        
        // Save the executable path to settings so the pure-background Python daemon 
        // knows how to launch the widget when compiled for Windows/Mac
        let settingsPath;
        if (app.isPackaged) {
            settingsPath = path.join(app.getPath('userData'), 'backend', 'settings.json');
        } else {
            settingsPath = path.join(__dirname, '..', 'settings.json');
        }
        
        if (fs.existsSync(settingsPath)) {
            try {
                const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
                settings.frontend_executable = app.isPackaged ? process.execPath : 'npm';
                fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 4));
            } catch(e) {}
        }
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

let wakeWindow = null;

function createWakeWindow() {
    if (wakeWindow) return;
    
    // Create a frameless, transparent window for the glowing orb
    wakeWindow = new BrowserWindow({
        width: 400,
        height: 250,
        transparent: true,
        frame: false,
        alwaysOnTop: true,
        hasShadow: false,
        resizable: false,
        focusable: true,
        skipTaskbar: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        }
    });

    wakeWindow.loadFile(path.join(__dirname, 'src', 'wake_popup.html'));
    
    // Position at the bottom center of the screen
    const { screen, net } = require('electron');
    const primaryDisplay = screen.getPrimaryDisplay();
    // Use absolute screen bounds instead of workArea to stick strictly to the bottom edge
    const { width, height } = primaryDisplay.bounds;
    
    wakeWindow.setBounds({
        x: Math.round(width / 2 - 200),
        y: Math.round(height - 230), // Adjusted to keep the bottom anchored since height is now 250
        width: 400,
        height: 250
    });
    
    wakeWindow.show(); // Show WITH focus so it can detect blur
    
    wakeWindow.on('blur', () => {
        // User clicked outside! Abort the AI voice and processing!
        try {
            const req = net.request({ method: 'POST', url: 'http://127.0.0.1:8932/api/stop' });
            req.on('response', () => {
                if (process.argv.includes('--widget')) app.quit();
            });
            req.on('error', () => {
                if (process.argv.includes('--widget')) app.quit();
            });
            req.end();
        } catch(e) {
            if (process.argv.includes('--widget')) app.quit();
        }
    });
}

ipcMain.on('show-wake-popup', () => {
    createWakeWindow();
});

ipcMain.on('hide-wake-popup', () => {
    if (wakeWindow) {
        wakeWindow.close();
        wakeWindow = null;
    }
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
