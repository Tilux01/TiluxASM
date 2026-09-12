import sys
import threading
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLineEdit
from PyQt5.QtCore import pyqtSignal, QObject
from brain import Brain
from voice import speak, listen

class WorkerSignals(QObject):
    """Signals to safely update the GUI from background audio threads."""
    message_ready = pyqtSignal(str, str) # sender, message
    status_update = pyqtSignal(str)
    
class AssistantApp(QWidget):
    def __init__(self):
        super().__init__()
        self.brain = Brain()
        self.signals = WorkerSignals()
        self.signals.message_ready.connect(self.append_message)
        self.signals.status_update.connect(self.update_mic_icon)
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Assistant')
        self.resize(500, 750)
        
        # Modern Dark Mode Styling (Catppuccin Mocha Palette)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTextEdit {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 8px;
                padding: 15px;
                font-size: 15px;
            }
            QLineEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 12px;
                font-size: 15px;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #11111b;
                border-radius: 8px;
                padding: 12px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
            QPushButton#micBtn {
                background-color: #f38ba8;
                font-size: 22px;
            }
            QPushButton#micBtn:hover {
                background-color: #eba0ac;
            }
        """)

        layout = QVBoxLayout()
        
        # Chat History Window
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)
        
        # Input Area (Bottom)
        input_layout = QHBoxLayout()
        
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type your message...")
        self.text_input.returnPressed.connect(self.send_text)
        input_layout.addWidget(self.text_input)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_text)
        input_layout.addWidget(self.send_btn)
        
        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setObjectName("micBtn")
        self.mic_btn.clicked.connect(self.start_voice)
        input_layout.addWidget(self.mic_btn)
        
        layout.addLayout(input_layout)
        self.setLayout(layout)
        
        self.append_message("System", "Assistant is online.<br>Click 🎤 to speak, or type a message.")
        
    def append_message(self, sender, text):
        """Adds a message to the chat display."""
        if sender == "System":
            color = "#a6adc8"
        elif sender == "You":
            color = "#a6e3a1" # Green
        else:
            color = "#89b4fa" # Blue
            
        html = f'<b><span style="color:{color}">{sender}:</span></b> {text}<br><br>'
        self.chat_display.insertHtml(html)
        # Auto-scroll to bottom
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
        
        # Reset Mic button
        self.mic_btn.setText("🎤")
        self.mic_btn.setEnabled(True)

    def update_mic_icon(self, icon):
        """Updates the microphone button icon (e.g., to a recording dot)."""
        self.mic_btn.setText(icon)

    def send_text(self):
        """Triggered when sending a typed message."""
        text = self.text_input.text().strip()
        if not text:
            return
        self.text_input.clear()
        self.append_message("You", text)
        self.process_command(text)
        
    def start_voice(self):
        """Triggered when clicking the mic button."""
        self.mic_btn.setEnabled(False)
        self.signals.status_update.emit("🔴") # Show recording dot
        # Start listening in a background thread so the UI doesn't freeze
        threading.Thread(target=self.listen_thread, daemon=True).start()
        
    def listen_thread(self):
        """Background thread for audio recording."""
        text = listen()
        if text:
            self.signals.message_ready.emit("You", text)
            self.process_thread(text)
        else:
            self.signals.message_ready.emit("System", "Did not catch that.")
            
    def process_command(self, text):
        """Wrapper to start the AI processing in a background thread."""
        self.mic_btn.setEnabled(False)
        self.signals.status_update.emit("⏳") # Show thinking icon
        threading.Thread(target=self.process_thread, args=(text,), daemon=True).start()
        
    def process_thread(self, text):
        """Background thread for AI generation and Text-To-Speech."""
        reply = self.brain.process_input(text)
        self.signals.message_ready.emit("Assistant", reply)
        speak(reply) # Speak it out loud (this blocks the thread, which is fine)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = AssistantApp()
    ex.show()
    sys.exit(app.exec_())
