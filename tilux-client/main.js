const { app, BrowserWindow, ipcMain, Notification, nativeImage, Menu, shell } = require('electron');

// Completely disable Electron default application menu across all windows
Menu.setApplicationMenu(null);
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

function findSystemPython() {
    if (process.platform !== 'win32') {
        return 'python3';
    }
    const candidates = [
        path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
        path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
        path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Python312', 'python.exe'),
        path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Python311', 'python.exe'),
        'C:\\Python312\\python.exe',
        'C:\\Python311\\python.exe'
    ];
    for (const cand of candidates) {
        if (fs.existsSync(cand)) {
            return `"${cand}"`;
        }
    }
    return 'python';
}

async function setupAndRunBackend() {
    let script, pyExe, backendCwd;

    if (app.isPackaged) {
        const userDataPath = app.getPath('userData');
        backendCwd = path.join(userDataPath, 'backend');
        const resourcesBackend = path.join(process.resourcesPath, 'backend');
        
        // Check for cross-platform pre-bundled standalone runtime
        const bundledPython = process.platform === 'win32'
            ? path.join(resourcesBackend, 'runtime', 'python.exe')
            : path.join(resourcesBackend, 'runtime', 'bin', 'python3');

        if (fs.existsSync(bundledPython)) {
            console.log(`[Tilux] Pre-bundled standalone Python runtime found: ${bundledPython}`);
            pyExe = bundledPython;
            script = path.join(resourcesBackend, 'server.py');
            
            // Ensure userData/backend directory exists for writable files (e.g. host_id, settings)
            if (!fs.existsSync(backendCwd)) {
                fs.mkdirSync(backendCwd, { recursive: true });
            }
            
            // Copy default configs if not already in userData
            for (const conf of ['settings.json', 'user_personal.json']) {
                const srcConf = path.join(resourcesBackend, conf);
                const destConf = path.join(backendCwd, conf);
                if (fs.existsSync(srcConf) && !fs.existsSync(destConf)) {
                    try { fs.copyFileSync(srcConf, destConf); } catch (_) {}
                }
            }
        } else {
            // Legacy / unbundled fallback
            const venvPath = path.join(backendCwd, 'venv');
            pyExe = process.platform === 'win32' ? 
                path.join(venvPath, 'Scripts', 'python.exe') : 
                path.join(venvPath, 'bin', 'python3');
                
            script = path.join(backendCwd, 'server.py');
            const setupCompleteFile = path.join(backendCwd, '.setup_complete');
            
            if (!fs.existsSync(setupCompleteFile) || !fs.existsSync(pyExe)) {
                console.log('First launch or broken install detected. Setting up backend...');
                
                if (fs.existsSync(venvPath)) {
                    fs.rmSync(venvPath, { recursive: true, force: true });
                }
                
                if (mainWindow) mainWindow.loadFile(path.join(__dirname, 'src', 'loading.html'));
                await new Promise(r => setTimeout(r, 1000));
                
                if (mainWindow) mainWindow.webContents.send('installation-status', 'Copying AI files to user data...');
                if (fs.existsSync(resourcesBackend)) {
                    copyDirectory(resourcesBackend, backendCwd);
                }
                
                try {
                    const pythonCmd = findSystemPython();
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
                    
                    await runSpawn(pythonCmd, ['-m', 'venv', 'venv'], backendCwd);
                    const pyCmd = process.platform === 'win32' ? path.join('venv', 'Scripts', 'python.exe') : path.join('.', 'venv', 'bin', 'python3');
                    if (mainWindow) mainWindow.webContents.send('installation-status', 'Running system setup (Dependencies & Engines)...');
                    await runSpawn(pyCmd, ['install.py'], backendCwd);
                    fs.writeFileSync(setupCompleteFile, 'done');
                    console.log('Setup complete.');
                    if (mainWindow) mainWindow.webContents.send('installation-status', 'Setup complete! Booting AI...');
                } catch (err) {
                    console.error('Setup error:', err);
                    if (mainWindow) mainWindow.webContents.send('installation-status', 'Setup Notice: ' + err.message + ' (Continuing to launch...)');
                }
                await new Promise(r => setTimeout(r, 1200));
            }
        }
    } else {
        // Dev mode
        backendCwd = path.join(__dirname, '..');
        script = path.join(backendCwd, 'server.py');
        pyExe = process.platform === 'win32' ? 
            path.join(backendCwd, 'venv', 'Scripts', 'python.exe') : 
            path.join(backendCwd, 'venv', 'bin', 'python3');
            
        if (!fs.existsSync(pyExe)) {
            pyExe = process.platform === 'win32' ? 'python' : 'python3';
        }
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
        const resourcesBackend = path.join(process.resourcesPath || '', 'backend');
        const customEnv = Object.assign({}, process.env, {
            TILUX_USER_DATA_DIR: backendCwd,
            PYTHONPATH: app.isPackaged ? `${resourcesBackend}${path.delimiter}${process.env.PYTHONPATH || ''}` : (process.env.PYTHONPATH || '')
        });
        try {
            pyProc = spawn(pyExe, spawnArgs, { 
                cwd: backendCwd, 
                shell: process.platform === 'win32',
                env: customEnv
            });
            console.log('Python backend spawned successfully.');
            pyProc.stdout.on('data', (data) => {
                console.log(`Python: ${data.toString()}`);
            });
            pyProc.stderr.on('data', (data) => {
                console.error(`Python Error: ${data.toString()}`);
            });
            pyProc.on('error', (err) => {
                console.error('Failed to spawn Python process:', err);
            });
        } catch (e) {
            console.error('Process spawn exception:', e);
        }
    } else {
        console.log('Python backend is already running on port 8932. Reusing active process.');
    }

    // Wait until backend is healthy and responding on port 8932 (up to 25 seconds)
    const startTime = Date.now();
    let backendReady = false;
    while (Date.now() - startTime < 25000) {
        if (await checkBackendRunning()) {
            backendReady = true;
            break;
        }
        await new Promise(r => setTimeout(r, 600));
    }
    
    if (!backendReady) {
        console.warn('Backend did not respond on port 8932 within timeout. Loading UI...');
    }

    if (mainWindow) {
        mainWindow.webContents.session.clearCache().then(() => {
            mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));
        });
    }
}

function exitPythonProcess() {
    if (pyProc) {
        pyProc.kill();
        pyProc = null;
    }
}

function createWindow () {
    const iconName = process.platform === 'win32' ? 'icon.ico' : 'icon.png';
    const iconPath = path.join(__dirname, 'src', iconName);
    const appIcon = nativeImage.createFromPath(iconPath);
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 900,
        minHeight: 600,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: true, // required for ipcRenderer in loading.html
            contextIsolation: false,
            devTools: false // Completely disables DevTools / console
        },
        autoHideMenuBar: true,
        title: "Tilux",
        icon: !appIcon.isEmpty() ? appIcon : iconPath
    });

    // Permanently remove window menu bar (prevents File/Edit/View/Help from popping up)
    mainWindow.removeMenu();
    mainWindow.setMenu(null);

    if (!appIcon.isEmpty() && typeof mainWindow.setIcon === 'function') {
        mainWindow.setIcon(appIcon);
    }

    // Intercept and block DevTools and view-source keyboard shortcuts
    mainWindow.webContents.on('before-input-event', (event, input) => {
        const key = (input.key || '').toLowerCase();
        const isDevToolsShortcut = 
            key === 'f12' ||
            (input.control && input.shift && (key === 'i' || key === 'j' || key === 'c')) ||
            (input.meta && input.alt && (key === 'i' || key === 'j' || key === 'c')) ||
            (input.control && key === 'u');
        
        if (isDevToolsShortcut) {
            event.preventDefault();
        }
    });

    // Failsafe: if DevTools somehow opens, close it immediately
    mainWindow.webContents.on('devtools-opened', () => {
        mainWindow.webContents.closeDevTools();
    });

    // Open any external web links in system browser, never inside the Electron window
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        if (url && (url.startsWith('http:') || url.startsWith('https:'))) {
            shell.openExternal(url);
        }
        return { action: 'deny' };
    });
    
    // Set a blank background while loading
    mainWindow.loadFile(path.join(__dirname, 'src', 'loading.html'));
}

app.whenReady().then(async () => {
    app.setAppUserModelId("com.tilux.asm");
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

function createWakeWindow(showImmediately = true) {
    if (wakeWindow && !wakeWindow.isDestroyed()) {
        if (showImmediately) {
            wakeWindow.show();
            wakeWindow.focus();
        }
        return;
    }

    const iconName = process.platform === 'win32' ? 'icon.ico' : 'icon.png';
    const iconPath = path.join(__dirname, 'src', iconName);
    const appIcon = nativeImage.createFromPath(iconPath);
    
    const winWidth = 400;
    const winHeight = 310;

    // Create a frameless, transparent window with ample headroom for ambient glow
    wakeWindow = new BrowserWindow({
        width: winWidth,
        height: winHeight,
        transparent: true,
        frame: false,
        alwaysOnTop: true,
        hasShadow: false,
        resizable: false,
        show: false,
        icon: !appIcon.isEmpty() ? appIcon : iconPath,
        focusable: true,
        skipTaskbar: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            devTools: false,
            backgroundThrottling: false
        }
    });

    wakeWindow.removeMenu();
    wakeWindow.setMenu(null);
    wakeWindow.webContents.on('devtools-opened', () => {
        wakeWindow.webContents.closeDevTools();
    });

    wakeWindow.loadFile(path.join(__dirname, 'src', 'wake_popup.html'));
    
    // Position at the bottom center of the screen with plenty of headroom at the top for glow
    const { screen } = require('electron');
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.bounds;
    
    wakeWindow.setBounds({
        x: Math.round(width / 2 - (winWidth / 2)),
        y: Math.round(height - 290),
        width: winWidth,
        height: winHeight
    });
    
    if (showImmediately) {
        wakeWindow.show();
        wakeWindow.focus();
    }
    
    wakeWindow.on('close', () => {
        try {
            const http = require('http');
            const req = http.request({
                hostname: '127.0.0.1',
                port: 8932,
                path: '/api/stop',
                method: 'POST'
            });
            req.on('error', () => {});
            req.end();
        } catch(err) {}
    });

    wakeWindow.on('closed', () => {
        wakeWindow = null;
    });
}

ipcMain.on('show-wake-popup', () => {
    createWakeWindow(true);
});

ipcMain.on('hide-wake-popup', () => {
    if (wakeWindow && !wakeWindow.isDestroyed()) {
        wakeWindow.close();
    }
});

ipcMain.on('open-chat-with-prompt', (event, prompt) => {
    if (wakeWindow && !wakeWindow.isDestroyed()) {
        wakeWindow.close();
    }
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.show();
        mainWindow.focus();
        mainWindow.webContents.send('auto-send-prompt', prompt);
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
