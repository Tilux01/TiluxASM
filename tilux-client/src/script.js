let selectedFiles = [];

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('chat-attachment-input');
    const previewContainer = document.getElementById('attachment-preview-container');

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            for (let i = 0; i < e.target.files.length; i++) {
                selectedFiles.push(e.target.files[i]);
            }
            renderPreviews();
            fileInput.value = '';
        });
    }

    // Support pasting images & files directly from clipboard (Ctrl+V / Cmd+V / Paste)
    document.addEventListener('paste', (e) => {
        const clipboardData = e.clipboardData || (e.originalEvent && e.originalEvent.clipboardData) || window.clipboardData;
        if (!clipboardData) return;

        const items = clipboardData.items;
        const files = clipboardData.files;
        let hasPastedFiles = false;

        if (items) {
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item.kind === 'file') {
                    const file = item.getAsFile();
                    if (file) {
                        let name = file.name;
                        if (!name || name === 'image.png') {
                            const ext = file.type.split('/')[1] || 'png';
                            name = `pasted_image_${Date.now()}_${i}.${ext}`;
                        }
                        const renamedFile = new File([file], name, { type: file.type });
                        selectedFiles.push(renamedFile);
                        hasPastedFiles = true;
                    }
                }
            }
        } else if (files && files.length > 0) {
            for (let i = 0; i < files.length; i++) {
                selectedFiles.push(files[i]);
                hasPastedFiles = true;
            }
        }

        if (hasPastedFiles) {
            e.preventDefault();
            renderPreviews();
            if (typeof showToast === 'function') {
                showToast('Image pasted into chat!', 'info');
            }
        }
    });
    
    window.toggleAttachmentMenu = function() {
        const menu = document.getElementById('attachment-menu');
        if (menu.style.display === 'none') {
            menu.style.display = 'block';
        } else {
            menu.style.display = 'none';
        }
    };
    
    window.triggerUpload = function(acceptType) {
        const fileInput = document.getElementById('chat-attachment-input');
        fileInput.accept = acceptType;
        fileInput.click();
        document.getElementById('attachment-menu').style.display = 'none';
    };
    
    // Hide menu if clicked outside
    document.addEventListener('click', function(event) {
        const menu = document.getElementById('attachment-menu');
        const btn = document.querySelector('button[onclick="toggleAttachmentMenu()"]');
        if (menu && btn && !menu.contains(event.target) && !btn.contains(event.target)) {
            menu.style.display = 'none';
        }
    });

    function renderPreviews() {
        if (!previewContainer) return;
        previewContainer.innerHTML = '';
        selectedFiles.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = 'attachment-preview-item';
            
            if (file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = URL.createObjectURL(file);
                item.appendChild(img);
            } else {
                const icon = document.createElement('i');
                icon.className = 'fa-solid fa-file-lines doc-icon';
                item.appendChild(icon);
            }
            
            const removeBtn = document.createElement('button');
            removeBtn.className = 'remove-btn';
            removeBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
            removeBtn.onclick = () => {
                selectedFiles.splice(index, 1);
                renderPreviews();
            };
            item.appendChild(removeBtn);
            previewContainer.appendChild(item);
        });
    }

    const inputField = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const micBtn = document.getElementById('mic-btn');
    
    const initialView = document.getElementById('initial-view');
    const chatHistory = document.getElementById('chat-history');
    const orbContainer = document.querySelector('.orb-container');
    
    let isFirstMessage = true;
    let isRecording = false;

    // Transition UI from Landing to Chat mode
    function transitionToChat() {
        if (!isFirstMessage) return;
        isFirstMessage = false;

        // Fade out initial text
        initialView.classList.add('fade-out');
        
        setTimeout(() => {
            initialView.style.display = 'none';
            // Show chat history
            chatHistory.classList.remove('hidden');
            // Move orb
            orbContainer.classList.add('docked');
            document.body.appendChild(orbContainer); // Move out of initial view to body for absolute positioning
        }, 500);
    }

    function sendDesktopNotification(text) {
        if (!text) return;
        const cleanText = text.replace(/[*_~`]/g, '').slice(0, 150) + (text.length > 150 ? '...' : '');
        if (window.electronAPI && window.electronAPI.showNotification) {
            window.electronAPI.showNotification(cleanText);
        }
    }

    function addMessage(sender, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender.toLowerCase()}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'msg-content';
        contentDiv.innerHTML = text; // allow basic HTML

        msgDiv.appendChild(contentDiv);
        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    window.scrollToBottom = function(e) {
        if (e && e.currentTarget) {
            try { e.currentTarget.blur(); } catch(err) {}
        }
        if (document.activeElement) {
            try { document.activeElement.blur(); } catch(err) {}
        }
        if (chatHistory) {
            chatHistory.scrollTo({ top: chatHistory.scrollHeight, behavior: 'smooth' });
        }
    };

    if (chatHistory) {
        chatHistory.addEventListener('scroll', () => {
            const scrollBtn = document.getElementById('scrollToBottomBtn');
            if (!scrollBtn) return;
            const distanceFromBottom = chatHistory.scrollHeight - chatHistory.scrollTop - chatHistory.clientHeight;
            if (distanceFromBottom > 100) {
                scrollBtn.classList.remove('hidden');
            } else {
                scrollBtn.classList.add('hidden');
            }
        });
    }

    function formatMarkdownAndProxyImages(text) {
        if (!text) return '';
        let parsed = typeof marked !== 'undefined' ? marked.parse(text) : text;
        const hostPrefix = 'http://127.0.0.1:8932';
        return parsed.replace(/src=["'](file:\/\/[^"']+|\/[^"']+|[A-Za-z]:\\[^"']+|[^\s"']+\.(?:png|jpg|jpeg|webp|gif|svg))["']/gi, (match, p1) => {
            if (p1.startsWith('http://') || p1.startsWith('https://') || p1.startsWith('data:')) {
                return match;
            }
            const cleanPath = p1.replace(/^file:\/\//, '');
            const proxyUrl = `${hostPrefix}/api/file?path=${encodeURIComponent(cleanPath)}`;
            return `src="${proxyUrl}" style="max-width: 100%; border-radius: 10px; margin-top: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);"`;
        });
    }

    function createAiMessage(loadingId) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message ai';
        msgDiv.id = `msg-${loadingId}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'msg-content';
        
        contentDiv.innerHTML = `<div id="events-container-${loadingId}" class="events-container"></div><div id="text-response-${loadingId}"></div>`;
        
        msgDiv.appendChild(contentDiv);
        chatHistory.appendChild(msgDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        
        return {
            updateEvents: function(events) {
                const container = document.getElementById(`events-container-${loadingId}`);
                if (!container || !events || events.length === 0) return;
                
                container.style.display = '';
                let didUpdate = false;
                events.forEach(ev => {
                    let el = document.getElementById(`event-${loadingId}-${ev.id}`);
                    if (!el) {
                        el = document.createElement('div');
                        el.id = `event-${loadingId}-${ev.id}`;
                        el.className = 'ai-event';
                        container.appendChild(el);
                        didUpdate = true;
                    }
                    
                    const existingDetails = el.querySelector('details');
                    const isOpen = existingDetails ? existingDetails.open : false;

                    if (ev.status === "running") {
                        if (el.dataset.status !== "running") {
                            el.dataset.status = "running";
                            let label = ev.type === "think" ? "Thinking..." : "Running a command...";
                            el.innerHTML = `<span class="event-running"><i class="fa-solid fa-circle-notch fa-spin"></i> ${label}</span>`;
                            didUpdate = true;
                        }
                    } else if (ev.status === "completed") {
                        const contentStr = String(ev.content || '');
                        if (el.dataset.completed !== "true" || el.dataset.contentHash !== contentStr) {
                            el.dataset.completed = "true";
                            el.dataset.contentHash = contentStr;
                            let durStr = ev.duration ? ` for ${ev.duration}` : "";
                            let label = ev.type === "think" ? `Thought${durStr}` : `Ran a command${durStr}`;
                            let defaultFallback = ev.type === "think" ? "Analyzed query and planned execution." : "Command completed successfully.";
                            let content = ev.content ? formatMarkdownAndProxyImages(ev.content) : defaultFallback;
                            el.innerHTML = `<details class="ai-steps-details"${isOpen ? ' open' : ''}><summary class="ai-steps-summary"><i class="fa-solid fa-chevron-right arrow-icon"></i> ${label}</summary><div class="ai-step"><i class="fa-solid fa-code-commit" style="margin-top: 4px;"></i> <div class="ai-step-content">${content}</div></div></details>`;
                            didUpdate = true;
                        }
                    }

                });
                if (didUpdate) {
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }
            },
            setReply: function(text) {
                const container = document.getElementById(`events-container-${loadingId}`);
                if (container) {
                    const runningEls = container.querySelectorAll('.event-running');
                    runningEls.forEach(el => {
                        const parent = el.closest('.ai-event');
                        if (parent && parent.dataset.completed !== "true") {
                            parent.remove();
                        }
                    });

                    if (container.children.length === 0) {
                        container.style.display = 'none';
                    } else {
                        container.style.display = '';
                    }
                }
                const textResponse = document.getElementById(`text-response-${loadingId}`);
                if (textResponse) {
                    textResponse.innerHTML = formatMarkdownAndProxyImages(text);
                }
                chatHistory.scrollTop = chatHistory.scrollHeight;
            },
            setError: function(text) {
                const textResponse = document.getElementById(`text-response-${loadingId}`);
                if (textResponse) {
                    textResponse.innerHTML = formatMarkdownAndProxyImages(text);
                }
            }
        };
    }

    let isProcessingText = false;
    let currentAbortController = null;
    let statusInterval = null;

    async function stopGeneration() {
        if (!isProcessingText) return;
        
        // Abort the fetch request
        if (currentAbortController) {
            currentAbortController.abort();
            currentAbortController = null;
        }
        
        // Tell the backend to stop
        try {
            await fetch('http://127.0.0.1:8932/api/stop', { method: 'POST' });
        } catch(e) {}
        
        // Reset UI
        isProcessingText = false;
        inputField.disabled = false;
        
        const sendIcon = document.getElementById('send-icon');
        if (sendIcon) {
            sendIcon.className = 'fa-solid fa-arrow-up';
            sendIcon.style.color = '';
        }
        
        if (statusInterval) {
            clearInterval(statusInterval);
            statusInterval = null;
        }
        
        inputField.focus();
    }

    async function sendText() {
        if (isProcessingText) return;
        const text = inputField.value.trim();
        if (!text && selectedFiles.length === 0) return;

        isProcessingText = true;
        
        const sendIcon = document.getElementById('send-icon');
        if (sendIcon) {
            sendIcon.className = 'fa-solid fa-stop';
            sendIcon.style.color = '#ef4444'; // Red color for stop
        }

        inputField.value = '';
        transitionToChat();
        
        let attachmentHtml = '';
        selectedFiles.forEach(file => {
            if (file.type.startsWith('image/')) {
                attachmentHtml += `<img src="${URL.createObjectURL(file)}" style="max-width: 400px; max-height: 300px; object-fit: contain; border-radius: 8px; margin-top: 10px; display: block;">`;
            } else {
                attachmentHtml += `<div style="background: rgba(255,255,255,0.1); padding: 8px; border-radius: 6px; margin-top: 10px; font-size: 12px;"><i class="fa-solid fa-file-lines"></i> ${file.name}</div>`;
            }
        });
        
        const finalMessageHtml = text + (attachmentHtml ? `<div style="display: flex; gap: 10px; flex-wrap: wrap;">${attachmentHtml}</div>` : '');
        addMessage('User', finalMessageHtml);
        
        const loadingId = Date.now();
        const aiMessage = createAiMessage(loadingId);

        let pollStatus = true;
        statusInterval = setInterval(async () => {
            if (!pollStatus) {
                if (statusInterval) clearInterval(statusInterval);
                return;
            }
            try {
                const res = await fetch('http://127.0.0.1:8932/api/status');
                const data = await res.json();
                if (data.events) {
                    aiMessage.updateEvents(data.events);
                }
            } catch (e) {
                // ignore
            }
        }, 500);

        try {
            currentAbortController = new AbortController();
            const formData = new FormData();
            formData.append('text', text);
            if (currentSessionId) {
                formData.append('session_id', currentSessionId);
            }
            selectedFiles.forEach(file => {
                formData.append('attachments', file);
            });
            
            // clear attachments after sending
            selectedFiles = [];
            if (document.getElementById('attachment-preview-container')) {
                document.getElementById('attachment-preview-container').innerHTML = '';
            }

            const response = await fetch('http://127.0.0.1:8932/api/chat', {
                method: 'POST',
                body: formData,
                signal: currentAbortController.signal
            });
            const data = await response.json();
            
            if (data.session_id) {
                currentSessionId = data.session_id;
                fetchDesktopHistory();
            }

            if (data.events) {
                aiMessage.updateEvents(data.events);
            }
            if (data.reply) {
                aiMessage.setReply(data.reply);
                sendDesktopNotification(data.reply);
            } else {
                aiMessage.setError(data.error || "Unknown Error");
            }
            
        } catch (e) {
            if (e.name === 'AbortError') {
                aiMessage.setError("Stopped by user.");
            } else {
                aiMessage.setError("Error connecting to backend.");
            }
        } finally {
            pollStatus = false;
            if (statusInterval) {
                clearInterval(statusInterval);
                statusInterval = null;
            }
            
            isProcessingText = false;
            inputField.disabled = false;
            
            const sendIcon = document.getElementById('send-icon');
            if (sendIcon) {
                sendIcon.className = 'fa-solid fa-arrow-up';
                sendIcon.style.color = '';
            }
            
            inputField.focus();
        }
    }

    async function startVoice() {
        if (isRecording) return; // Prevent double clicks
        
        isRecording = true;
        micBtn.classList.add('recording');
        micBtn.innerHTML = '<i class="fa-solid fa-stop"></i>';
        inputField.placeholder = "Listening...";
        inputField.disabled = true;

        const loadingId = Date.now();
        let aiMessage = null;
        let pollStatus = false;
        let statusInterval = null;
        
        // Placeholder for user transcript so it appears ABOVE the AI response
        const userMsgPlaceholder = document.createElement('div');
        chatHistory.appendChild(userMsgPlaceholder);

        try {
            setTimeout(() => {
                if (!isRecording) return;
                pollStatus = true;
                aiMessage = createAiMessage(loadingId);
                
                statusInterval = setInterval(async () => {
                    if (!pollStatus) {
                        clearInterval(statusInterval);
                        return;
                    }
                    try {
                        const res = await fetch('http://127.0.0.1:8932/api/status');
                        const data = await res.json();
                        if (data.events && aiMessage) {
                            aiMessage.updateEvents(data.events);
                        }
                    } catch (e) {}
                }, 500);
            }, 3000); // Wait 3s before showing status

            const response = await fetch('http://127.0.0.1:8932/api/voice', {
                method: 'POST'
            });
            const data = await response.json();
            
            pollStatus = false;
            if (statusInterval) clearInterval(statusInterval);
            
            transitionToChat();
            
            if (data.text) {
                userMsgPlaceholder.className = 'message user';
                userMsgPlaceholder.innerHTML = `<div class="msg-content">${data.text}</div>`;
                
                if (!aiMessage) {
                    aiMessage = createAiMessage(loadingId);
                }
                if (data.events) {
                    aiMessage.updateEvents(data.events);
                }
                aiMessage.setReply(data.reply || data.error);
                if (data.reply) sendDesktopNotification(data.reply);
            } else {
                userMsgPlaceholder.remove();
                if (aiMessage) aiMessage.setError("Did not catch that. Please try again.");
                else showToast(data.error || "Did not catch that. Please try again.", "error");
            }
        } catch (e) {
            pollStatus = false;
            if (statusInterval) clearInterval(statusInterval);
            userMsgPlaceholder.remove();
            if (aiMessage) {
                 aiMessage.setError("Voice recording failed. Check microphone permissions.");
            } else {
                 showToast("Voice recording failed. Check microphone permissions.", "error");
            }
        }

        // Reset UI
        isRecording = false;
        micBtn.classList.remove('recording');
        micBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
        inputField.placeholder = "Ask Anything...";
        inputField.disabled = false;
        inputField.focus();
    }

    // New Functionalities
    window.clearChat = function() {
        chatHistory.innerHTML = "";
        addMessage('AI', 'Memory cleared. How can I assist you now?');
        showToast("Memory cleared successfully", "success");
    };

    window.killAudio = async function() {
        await fetch('http://127.0.0.1:8932/api/kill_audio', { method: 'POST' });
        showToast("Audio playback stopped", "success");
        console.log("Audio killed");
    };

    window.showToast = function(message, type = "info") {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        let icon = '<i class="fa-solid fa-circle-info"></i>';
        if (type === 'error') icon = '<i class="fa-solid fa-triangle-exclamation"></i>';
        if (type === 'success') icon = '<i class="fa-solid fa-circle-check"></i>';
        
        toast.innerHTML = `${icon} <span>${message}</span>`;
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => {
                if (toast.parentNode === container) {
                    container.removeChild(toast);
                }
            }, 400); // Wait for animation to finish
        }, 3000); // Show for 3 seconds
    };

    window.triggerAction = async function(action) {
        await fetch('http://127.0.0.1:8932/api/trigger', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action })
        });
    };

    async function fetchSystemStats() {
        try {
            const res = await fetch('http://127.0.0.1:8932/api/system');
            const data = await res.json();
            document.getElementById('cpu-val').innerText = `${data.cpu.toFixed(1)}%`;
            document.getElementById('cpu-fill').style.width = `${data.cpu}%`;
            document.getElementById('ram-val').innerText = `${data.ram.toFixed(1)}%`;
            document.getElementById('ram-fill').style.width = `${data.ram}%`;
            document.getElementById('swap-val').innerText = `${data.swap.toFixed(1)}%`;
            document.getElementById('swap-fill').style.width = `${data.swap}%`;
            document.getElementById('net-down').innerText = data.download;
            document.getElementById('net-up').innerText = data.upload;
            
            const list = document.getElementById('process-list');
            list.innerHTML = "";
            if (data.top_processes && data.top_processes.length > 0) {
                data.top_processes.forEach(proc => {
                    const li = document.createElement('li');
                    li.innerHTML = `<strong>${proc.name}</strong> <span style="float:right;">${proc.cpu}% CPU | ${proc.mem}% RAM</span>`;
                    list.appendChild(li);
                });
            } else {
                list.innerHTML = "<li>No processes found.</li>";
            }
        } catch (e) {
            console.error("Failed to load system stats", e);
        }
    }

    // --- Settings Logic ---
    let settingsOpen = false;

    window.toggleSettings = function() {
        const chatContainer = document.querySelector('.chat-container');
        const settingsView = document.getElementById('settings-view');
        
        settingsOpen = !settingsOpen;
        if (settingsOpen) {
            chatContainer.style.display = 'none';
            settingsView.style.display = 'block';
            loadSettings();
        } else {
            settingsView.style.display = 'none';
            chatContainer.style.display = 'flex';
        }
    };

    window.fetchQrPair = async function() {
        try {
            const res = await fetch('http://127.0.0.1:8932/api/qr_pair');
            const data = await res.json();
            if (data.qr_image) {
                const qrImg = document.getElementById('qr-img');
                const qrLoading = document.getElementById('qr-loading');
                if (qrImg) {
                    qrImg.src = data.qr_image;
                    qrImg.style.display = 'block';
                }
                if (qrLoading) qrLoading.style.display = 'none';
                if (document.getElementById('remote-host-val')) document.getElementById('remote-host-val').innerText = data.ip;
                if (document.getElementById('remote-token-val')) document.getElementById('remote-token-val').innerText = data.token;
            }
        } catch(e) {
            console.error("Error fetching QR pair:", e);
        }
    };

    window.togglePassVisibility = function(inputId, btn) {
        const input = document.getElementById(inputId);
        if (!input) return;
        if (input.type === 'password') {
            input.type = 'text';
            if (btn) btn.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
        } else {
            input.type = 'password';
            if (btn) btn.innerHTML = '<i class="fa-solid fa-eye"></i>';
        }
    };

    async function loadSettings() {
        try {
            fetchQrPair();
            const res = await fetch('http://127.0.0.1:8932/api/settings', { cache: 'no-store' });
            const data = await res.json();
            
            // Check setup complete logic
            if (data.setup_complete === false) {
                document.getElementById('setup-wizard').style.display = 'flex';
            }
            
            document.getElementById('tts-toggle').checked = data.tts_enabled;
            document.getElementById('tts-voice').value = data.tts_voice || 'en-US-AriaNeural';
            if (document.getElementById('ai-tone')) {
                document.getElementById('ai-tone').value = data.ai_tone || 'Sassy Gen-Z';
            }
            if (document.getElementById('sudo-pass-input')) {
                document.getElementById('sudo-pass-input').value = data.sudo_password || '';
            }
            let speed = data.tts_speed || '+20%';
            speed = parseInt(speed.replace('%', '').replace('+', ''));
            document.getElementById('tts-speed').value = speed;
            document.getElementById('speed-val-display').innerText = (speed >= 0 ? '+' : '') + speed + '%';
        } catch(e) {
            console.error("Error loading settings:", e);
        }
    }

    window.saveSettings = async function(additionalData = {}) {
        const speedVal = document.getElementById('tts-speed').value;
        let toneVal = 'Sassy Gen-Z';
        if (document.getElementById('ai-tone')) {
            toneVal = document.getElementById('ai-tone').value;
        }
        let sudoPassVal = '';
        if (document.getElementById('sudo-pass-input')) {
            sudoPassVal = document.getElementById('sudo-pass-input').value;
        }
        
        let data = {
            tts_enabled: document.getElementById('tts-toggle').checked,
            tts_voice: document.getElementById('tts-voice').value,
            tts_speed: (speedVal >= 0 ? '+' : '') + speedVal + '%',
            ai_tone: toneVal,
            sudo_password: sudoPassVal,
            ...additionalData
        };
        try {
            await fetch('http://127.0.0.1:8932/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            // Sync settings to Firebase Realtime Database for current user
            if (window.currentUser && typeof firebase !== 'undefined') {
                try {
                    firebase.database().ref('users/' + window.currentUser.uid + '/personal_data/settings').update(data);
                } catch(e) {}
            }
        } catch(e) {
            console.error("Error saving settings:", e);
        }
    };

    // Start background fetching
    setInterval(fetchSystemStats, 3000); // Update stats every 3s
    fetchSystemStats(); // Initial fetch

    // Event Listeners
    sendBtn.addEventListener('click', () => {
        if (isProcessingText) stopGeneration();
        else sendText();
    });
    inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !isProcessingText) sendText();
    });
    micBtn.addEventListener('click', startVoice);

    // --- SETUP WIZARD LOGIC ---
    let selectedTone = 'Sassy Gen-Z';

    window.nextWizardStep = function(stepNum) {
        document.querySelectorAll('.wizard-step').forEach(el => el.classList.remove('active'));
        document.getElementById('wizard-step-' + stepNum).classList.add('active');
    };

    window.selectToneCard = function(el, tone) {
        document.querySelectorAll('.tone-card').forEach(c => c.classList.remove('selected'));
        el.classList.add('selected');
        selectedTone = tone;
    };

    window.startInstallation = function() {
        // Save the tone first
        if (document.getElementById('ai-tone')) document.getElementById('ai-tone').value = selectedTone;
        saveSettings();
        
        nextWizardStep(3);
        const term = document.getElementById('wizard-terminal');
        term.innerHTML = "Starting universal dependency installer...\n";
        
        const source = new EventSource('http://127.0.0.1:8932/api/install');
        source.onmessage = function(event) {
            if (event.data === "[INSTALL_COMPLETE]") {
                source.close();
                nextWizardStep(4);
            } else {
                term.innerHTML += event.data + "\n";
                term.scrollTop = term.scrollHeight; // Auto-scroll
            }
        };
        source.onerror = function() {
            term.innerHTML += "\n[Error connecting to installation stream. Backend might be restarting.]\n";
            source.close();
            // Just move to finish after a few seconds if error
            setTimeout(() => nextWizardStep(4), 3000);
        };
    };

    window.finishWizard = function() {
        // Just hide the wizard, settings were already saved as complete by the backend
        document.getElementById('setup-wizard').style.display = 'none';
        showToast("Setup complete! Tilux is ready.", "success");
        loadSettings(); // Refresh UI
    };

    // --- DESKTOP STRICT FIREBASE AUTH GATE & PERSONAL DATA SYNC ENGINE ---
    const desktopAuthOverlay = document.getElementById('desktop-auth-overlay');
    const authErrorMsg = document.getElementById('auth-error-msg');
    const authErrorText = document.getElementById('auth-error-text');
    let currentAuthMode = 'login'; // 'login' or 'register'
    window.currentUser = null;
    
    // Initialize Firebase in Electron Client
    const firebaseConfig = {
      apiKey: "AIzaSyAQ1ffdL36D8Bw3xA4fOj1boPJlqhPR4p4",
      authDomain: "tiluxasm.firebaseapp.com",
      databaseURL: "https://tiluxasm-default-rtdb.firebaseio.com",
      projectId: "tiluxasm",
      storageBucket: "tiluxasm.firebasestorage.app",
      messagingSenderId: "686558431377",
      appId: "1:686558431377:web:64786056989860a2039730",
      measurementId: "G-Q7Y0B754HX"
    };

    if (typeof firebase !== 'undefined' && !firebase.apps.length) {
      firebase.initializeApp(firebaseConfig);
    }

    // Friendly Human Error Sanitizer
    function sanitizeFirebaseError(err) {
      const code = err.code || '';
      if (code === 'auth/invalid-credential' || code === 'auth/user-not-found' || code === 'auth/wrong-password') {
        return "Invalid email or password. Please check your details and try again.";
      }
      if (code === 'auth/email-already-in-use') {
        return "An account with this email address already exists. Please sign in instead.";
      }
      if (code === 'auth/weak-password') {
        return "Password is too weak. Please use at least 6 characters.";
      }
      if (code === 'auth/invalid-email') {
        return "Please enter a valid email address.";
      }
      if (code === 'auth/too-many-requests') {
        return "Too many failed attempts. Please wait a moment and try again.";
      }
      if (code === 'auth/network-request-failed') {
        return "Network connection error. Please check your internet connection.";
      }
      let raw = err.message || "An authentication error occurred. Please try again.";
      raw = raw.replace(/^Firebase:\s*/i, '').replace(/\s*\(auth\/[a-z-]+\)\.?$/i, '');
      return raw || "Authentication error. Please try again.";
    }

    window.showAuthOverlay = function() {
      if (desktopAuthOverlay) desktopAuthOverlay.style.display = 'flex';
    };

    window.hideAuthOverlay = function() {
      if (desktopAuthOverlay) desktopAuthOverlay.style.display = 'none';
    };

    window.switchAuthTab = function(mode) {
      currentAuthMode = mode;
      if (authErrorMsg) authErrorMsg.style.display = 'none';
      
      const title = document.getElementById('auth-card-title');
      const sub = document.getElementById('auth-card-sub');
      const btnText = document.getElementById('auth-btn-text');
      const rowDual = document.getElementById('row-dual-name');
      const footerPrompt = document.getElementById('auth-footer-prompt');
      const stepLabel = document.getElementById('step-label-1');

      if (mode === 'login') {
        if (title) title.textContent = "Sign In Account";
        if (sub) sub.textContent = "Enter your credentials to access your account.";
        if (btnText) btnText.textContent = "Log In";
        if (rowDual) rowDual.style.display = 'none';
        if (stepLabel) stepLabel.textContent = "Sign in to your account";
        if (footerPrompt) {
          footerPrompt.innerHTML = `Don't have an account? <a href="#" id="link-toggle-auth" onclick="switchAuthTab('register'); return false;">Sign up</a>`;
        }
      } else {
        if (title) title.textContent = "Sign Up Account";
        if (sub) sub.textContent = "Enter your personal data to create your account.";
        if (btnText) btnText.textContent = "Sign Up";
        if (rowDual) rowDual.style.display = 'grid';
        if (stepLabel) stepLabel.textContent = "Sign up your account";
        if (footerPrompt) {
          footerPrompt.innerHTML = `Already have an account? <a href="#" id="link-toggle-auth" onclick="switchAuthTab('login'); return false;">Log in</a>`;
        }
      }
    };

    window.togglePasswordVisibility = function(inputId, btnEl) {
      const pwdInput = document.getElementById(inputId);
      const icon = btnEl.querySelector('i');
      if (pwdInput.type === 'password') {
        pwdInput.type = 'text';
        icon.className = 'fa-solid fa-eye-slash';
      } else {
        pwdInput.type = 'password';
        icon.className = 'fa-solid fa-eye';
      }
    };

    // Update Account Profile UI card dynamically
    window.updateAccountProfileUI = function(user) {
      const nameEl = document.getElementById('account-user-name');
      const statusEl = document.getElementById('account-user-status');
      const uidEl = document.getElementById('account-user-uid');
      const actionArea = document.getElementById('account-action-area');
      const avatarIcon = document.getElementById('account-avatar-icon');

      if (user) {
        const emailStr = user.email || "Authenticated User";
        if (nameEl) nameEl.textContent = emailStr;
        if (statusEl) {
          statusEl.innerHTML = `<i class="fa-solid fa-circle-check" style="color: #10b981;"></i> Authenticated & Synchronized`;
          statusEl.style.color = "#10b981";
        }
        if (uidEl) {
          uidEl.textContent = `UID: ${user.uid}`;
          uidEl.style.display = 'block';
        }
        if (avatarIcon) avatarIcon.className = "fa-solid fa-user-astronaut";
        if (actionArea) {
          actionArea.innerHTML = `
            <button class="btn-outline" onclick="signOutUser()" style="border-color: rgba(239, 68, 68, 0.4); color: #f87171; background: rgba(239, 68, 68, 0.1); font-size: 13px; padding: 8px 16px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s;">
              <i class="fa-solid fa-right-from-bracket"></i> Sign Out
            </button>
          `;
        }
      } else {
        if (nameEl) nameEl.textContent = "Guest User";
        if (statusEl) {
          statusEl.innerHTML = `<i class="fa-solid fa-circle-dot" style="font-size: 10px; color: #ef4444;"></i> Not signed in`;
          statusEl.style.color = "#a1a1aa";
        }
        if (uidEl) uidEl.style.display = 'none';
        if (actionArea) {
          actionArea.innerHTML = `
            <button class="btn-outline" onclick="showAuthOverlay()" style="border-color: rgba(0, 242, 254, 0.4); color: #00F2FE; background: rgba(0, 242, 254, 0.08); font-size: 13px; padding: 8px 16px; border-radius: 8px; cursor: pointer;">
              <i class="fa-solid fa-right-to-bracket"></i> Sign In / Register
            </button>
          `;
        }
      }
    };

    // Firebase Personal Data Sync Engine (stores user profile, preferences, and personal JSON)
    async function syncUserDataWithFirebase(user) {
      if (!user || typeof firebase === 'undefined') return;
      try {
        const dbRef = firebase.database().ref('users/' + user.uid + '/personal_data');
        const snapshot = await dbRef.once('value');
        let personalData = snapshot.val();

        if (!personalData) {
          // Initialize default personal JSON for new user
          personalData = {
            email: user.email,
            uid: user.uid,
            created_at: Date.now(),
            last_login: Date.now(),
            settings: {
              tts_enabled: true,
              tts_voice: "en-US-AriaNeural",
              tts_speed: "+20%",
              ai_tone: "Sassy Gen-Z"
            },
            memory: {
              recent_commands: [],
              preferences: {}
            }
          };
          await dbRef.set(personalData);
        } else {
          // Update last login timestamp
          await dbRef.update({ last_login: Date.now() });
        }

        // Save personal JSON file locally & send to Python backend
        localStorage.setItem('tilux_personal_data', JSON.stringify(personalData));
        await fetch('http://127.0.0.1:8932/api/sync_user_personal', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(personalData)
        }).catch(e => console.error(e));

        // Restore settings into UI if available
        if (personalData.settings) {
          if (document.getElementById('tts-toggle')) document.getElementById('tts-toggle').checked = personalData.settings.tts_enabled;
          if (document.getElementById('tts-voice')) document.getElementById('tts-voice').value = personalData.settings.tts_voice || 'en-US-AriaNeural';
          if (document.getElementById('ai-tone')) document.getElementById('ai-tone').value = personalData.settings.ai_tone || 'Sassy Gen-Z';
        }
      } catch (err) {
        console.error("Error syncing personal data with Firebase:", err);
      }
    }

    // Complete User Sign Out & Data Erasure
    window.signOutUser = async function() {
      try {
        if (typeof showToast === 'function') {
          showToast("Signing out and purging local session data...", "info");
        }

        // 1. Sync logout timestamp to Firebase if online
        if (window.currentUser && typeof firebase !== 'undefined') {
          try {
            const dbRef = firebase.database().ref('users/' + window.currentUser.uid + '/personal_data');
            await dbRef.update({ last_logout: Date.now() });
          } catch(e) {}
        }

        // 2. Erase all local credentials, localStorage & cached state
        localStorage.clear();

        // 3. Request Python backend to erase local user session & memory file
        await fetch('http://127.0.0.1:8932/api/clear_user_session', { method: 'POST' }).catch(e => console.error(e));

        // 4. Firebase Auth Sign Out
        if (typeof firebase !== 'undefined') {
          await firebase.auth().signOut();
        }

        window.currentUser = null;
        updateAccountProfileUI(null);
        showAuthOverlay();

        if (typeof showToast === 'function') {
          showToast("Signed out successfully. All local credentials & user data erased.", "success");
        }
      } catch (err) {
        console.error("Error during sign out:", err);
        if (typeof showToast === 'function') {
          showToast("Error signing out: " + err.message, "error");
        }
      }
    };

    window.checkDesktopAuthSession = function() {
      if (typeof firebase === 'undefined') return;
      
      firebase.auth().onAuthStateChanged(async (user) => {
        window.currentUser = user;
        if (user) {
          console.log('[Desktop Auth] Logged in as:', user.email);
          localStorage.setItem('tilux_pc_user_email', user.email);
          hideAuthOverlay();
          updateAccountProfileUI(user);
          await syncUserDataWithFirebase(user);
        } else {
          console.log('[Desktop Auth] No active session. Displaying Auth Gate.');
          localStorage.clear();
          updateAccountProfileUI(null);
          showAuthOverlay();
        }
      });
    };

    window.submitAuthForm = async function() {
      const email = document.getElementById('pc-auth-email').value.trim();
      const pass = document.getElementById('pc-auth-password').value.trim();
      const btnSubmit = document.getElementById('pc-btn-submit');
      const btnText = document.getElementById('auth-btn-text');

      if (authErrorMsg) authErrorMsg.style.display = 'none';

      if (!email || !pass) {
        if (authErrorText) authErrorText.textContent = "Please enter both Email Address and Password.";
        if (authErrorMsg) authErrorMsg.style.display = 'flex';
        return;
      }

      if (pass.length < 6) {
        if (authErrorText) authErrorText.textContent = "Password must be at least 6 characters.";
        if (authErrorMsg) authErrorMsg.style.display = 'flex';
        return;
      }

      btnSubmit.disabled = true;
      btnText.textContent = currentAuthMode === 'login' ? "Signing in..." : "Creating Account...";

      try {
        if (currentAuthMode === 'login') {
          await firebase.auth().signInWithEmailAndPassword(email, pass);
        } else {
          await firebase.auth().createUserWithEmailAndPassword(email, pass);
          if (typeof showToast === 'function') showToast("Account Created Successfully!", "success");
        }
      } catch (err) {
        if (authErrorText) authErrorText.textContent = sanitizeFirebaseError(err);
        if (authErrorMsg) authErrorMsg.style.display = 'flex';
      } finally {
        btnSubmit.disabled = false;
        btnText.textContent = currentAuthMode === 'login' ? "Sign In" : "Create Account";
      }
    };

    // Initialize Auth Session Check on App Startup
    checkDesktopAuthSession();

    // --- DESKTOP SIDEBAR TAB & CHAT HISTORY MANAGER ---
    window.switchSidebarTab = function(tab) {
        const sysBtn = document.getElementById('tab-btn-system');
        const histBtn = document.getElementById('tab-btn-history');
        const sysPanel = document.getElementById('sidebar-system-panel');
        const histPanel = document.getElementById('sidebar-history-panel');

        if (tab === 'system') {
            if (sysBtn) sysBtn.classList.add('active');
            if (histBtn) histBtn.classList.remove('active');
            if (sysPanel) sysPanel.style.display = '';
            if (histPanel) histPanel.style.display = 'none';
        } else {
            if (histBtn) histBtn.classList.add('active');
            if (sysBtn) sysBtn.classList.remove('active');
            if (histPanel) histPanel.style.display = '';
            if (sysPanel) sysPanel.style.display = 'none';
            fetchDesktopHistory();
        }
    };

    window.fetchDesktopHistory = async function() {
        const container = document.getElementById('desktop-history-list');
        if (!container) return;
        try {
            const res = await fetch('http://127.0.0.1:8932/api/history');
            const sessions = await res.json();
            renderDesktopHistory(sessions);
        } catch(e) {
            container.innerHTML = '<div class="history-empty">Failed to load history</div>';
        }
    };

    function renderDesktopHistory(sessions) {
        const container = document.getElementById('desktop-history-list');
        if (!container) return;
        container.innerHTML = '';
        if (!sessions || sessions.length === 0) {
            container.innerHTML = '<div class="history-empty"><i class="fa-solid fa-comments"></i> No past conversations yet</div>';
            return;
        }
        sessions.forEach(s => {
            const item = document.createElement('div');
            item.className = `history-item${s.id === currentSessionId ? ' active' : ''}`;
            item.onclick = () => loadHistorySession(s.id);
            
            item.innerHTML = `
                <div class="history-info">
                    <span class="history-title"><i class="fa-solid fa-message" style="margin-right: 6px; font-size: 11px; color: var(--accent);"></i> ${s.title}</span>
                    <span class="history-date">${s.timestamp}</span>
                </div>
                <button type="button" class="history-del-btn" title="Delete conversation" onclick="deleteHistorySession('${s.id}', event)">
                    <i class="fa-solid fa-trash"></i>
                </button>
            `;
            container.appendChild(item);
        });
    }

    window.loadHistorySession = async function(sessionId) {
        currentSessionId = sessionId;
        try {
            const res = await fetch(`http://127.0.0.1:8932/api/history/${sessionId}`);
            const session = await res.json();
            if (session && session.messages) {
                isFirstMessage = false;
                if (initialView) {
                    initialView.classList.add('fade-out');
                    initialView.style.display = 'none';
                }
                if (chatHistory) {
                    chatHistory.classList.remove('hidden');
                    chatHistory.innerHTML = '';
                }
                if (orbContainer) {
                    orbContainer.classList.add('docked');
                    if (initialView && initialView.contains(orbContainer)) {
                        document.body.appendChild(orbContainer);
                    }
                }
                session.messages.forEach(msg => {
                    if (msg.sender === 'User') {
                        addMessage('User', msg.text);
                    } else {
                        addMessage('AI', formatMarkdownAndProxyImages(msg.text));
                    }
                });
                if (chatHistory) chatHistory.scrollTop = chatHistory.scrollHeight;
                fetchDesktopHistory();
            }
        } catch(e) {
            console.error('Error loading history session:', e);
        }
    };

    window.startNewChat = async function() {
        currentSessionId = null;
        isFirstMessage = true;
        try {
            await fetch('http://127.0.0.1:8932/api/history/new', { method: 'POST' });
        } catch(e) {}
        if (chatHistory) {
            chatHistory.innerHTML = '';
            chatHistory.classList.add('hidden');
        }
        if (initialView) {
            initialView.classList.remove('hidden');
            initialView.classList.remove('fade-out');
            initialView.style.display = '';
        }
        if (orbContainer) orbContainer.classList.remove('docked');
        fetchDesktopHistory();
    };

    window.deleteHistorySession = async function(sessionId, event) {
        if (event) event.stopPropagation();
        try {
            await fetch(`http://127.0.0.1:8932/api/history/${sessionId}`, { method: 'DELETE' });
            fetchDesktopHistory();
        } catch(e) {}
    };

    // Load desktop history on app start
    fetchDesktopHistory();
});

let currentSessionId = null;
