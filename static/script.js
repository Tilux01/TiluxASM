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
                    
                    if (ev.status === "running") {
                        let label = ev.type === "think" ? "Thinking..." : "Running a command...";
                        el.innerHTML = `<span class="event-running"><i class="fa-solid fa-circle-notch fa-spin"></i> ${label}</span>`;
                    } else if (ev.status === "completed" && el.dataset.completed !== "true") {
                        el.dataset.completed = "true";
                        let label = ev.type === "think" ? "Thought" : "Ran a command";
                        let content = ev.content ? (typeof marked !== 'undefined' ? marked.parse(ev.content) : ev.content.replace(/</g, "&lt;").replace(/>/g, "&gt;")) : "Finished thinking.";
                        let openAttr = ev.type === "think" ? " open" : "";
                        el.innerHTML = `<details class="ai-steps-details"${openAttr}><summary class="ai-steps-summary"><i class="fa-solid fa-chevron-right arrow-icon"></i> ${label}</summary><div class="ai-step"><i class="fa-solid fa-code-commit" style="margin-top: 4px;"></i> <div class="ai-step-content">${content}</div></div></details>`;
                        didUpdate = true;
                    }
                });
                if (didUpdate) {
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }
            },
            setReply: function(text) {
                const textResponse = document.getElementById(`text-response-${loadingId}`);
                if (textResponse) {
                    textResponse.innerHTML = typeof marked !== 'undefined' ? marked.parse(text) : text;
                }
                chatHistory.scrollTop = chatHistory.scrollHeight;
            },
            setError: function(text) {
                const textResponse = document.getElementById(`text-response-${loadingId}`);
                if (textResponse) {
                    textResponse.innerHTML = typeof marked !== 'undefined' ? marked.parse(text) : text;
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
            const formData = new FormData();
            formData.append('text', text);
            selectedFiles.forEach(file => {
                formData.append('attachments', file);
            });
            
            // clear attachments after sending
            selectedFiles = [];
            if (document.getElementById('attachment-preview-container')) {
                document.getElementById('attachment-preview-container').innerHTML = '';
            }

            currentAbortController = new AbortController();
            const response = await fetch('http://127.0.0.1:8932/api/chat', {
                method: 'POST',
                body: formData,
                signal: currentAbortController.signal
            });
            const data = await response.json();
            
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

    async function loadSettings() {
        try {
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
        
        let data = {
            tts_enabled: document.getElementById('tts-toggle').checked,
            tts_voice: document.getElementById('tts-voice').value,
            tts_speed: (speedVal >= 0 ? '+' : '') + speedVal + '%',
            ai_tone: toneVal,
            ...additionalData
        };
        try {
            await fetch('http://127.0.0.1:8932/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
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
});
