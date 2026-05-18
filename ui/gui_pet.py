import os
import sys
import random
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect
from PyQt5.QtGui import QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QComboBox, QLineEdit, QPushButton, QHBoxLayout

# CRITICAL HIGH-DPI WORKSPACE ALIGNMENT FIX
if sys.platform == 'win32':
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    os.environ["QT_SCREEN_SCALE_FACTORS"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "1"

from core.config import LOCK_FILE
from core.llm_client import LintLLMClient


class FloatingCatPet(QWidget):
    def __init__(self):
        super().__init__()
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.anim_dir = os.path.join(self.base_dir, "anim")
        self.llm = LintLLMClient()

        self.animation_profiles = {
            "default": {"file": "idle.png", "width": 32, "height": 32, "frames": 10},
            "lie": {"file": "lie.png", "width": 32, "height": 32, "frames": 12},
            "sleep": {"file": "sleep.png", "width": 32, "height": 32, "frames": 4},
            "yawn": {"file": "yawn.png", "width": 32, "height": 32, "frames": 8},
            "angry": {"file": "angry2.png", "width": 32, "height": 32, "frames": 9}
        }
        self.current_state = "default"
        self.current_frame = 0
        self.sprite_scale = 4
        self.loaded_sprites = {}
        self.load_assets()
        self.init_ui()

        self.frame_timer = QTimer()
        self.frame_timer.timeout.connect(self.cycle_frame)
        self.frame_timer.start(125)

        self.lock_timer = QTimer()
        self.lock_timer.timeout.connect(self.check_lock)
        self.lock_timer.start(800)

        self.chatter_timer = QTimer()
        self.chatter_timer.timeout.connect(self.passive_chatter)
        self.chatter_timer.start(45000)

        self.drag_pos = QPoint()

    def load_assets(self):
        for s, info in self.animation_profiles.items():
            path = os.path.join(self.anim_dir, info["file"])
            if os.path.exists(path):
                self.loaded_sprites[s] = {"pixmap": QPixmap(path), "w": info["width"], "h": info["height"],
                                          "total": info["frames"], "fallback": False}
            else:
                self.loaded_sprites[s] = {"fallback": True}

    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Main overall layout frame container
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(4)

        # ─── MIDDLE ROW: SPEECH BUBBLE OFFSET LEFT OF LINT ───
        self.middle_row_layout = QHBoxLayout()
        self.middle_row_layout.setContentsMargins(0, 0, 0, 0)
        self.middle_row_layout.setSpacing(4)

        # Left-aligned speech bubble
        self.bubble_label = QLabel("*staring*")
        self.bubble_label.setStyleSheet(
            "background-color: rgba(33, 37, 43, 235); color: #abb2bf; "
            "border: 1px solid #5c6370; border-radius: 5px; padding: 4px; "
            "font-family: monospace; font-size: 11px;"
        )
        self.bubble_label.setFixedWidth(136)
        self.bubble_label.setFixedHeight(128)  # Matches cat height
        self.bubble_label.setWordWrap(True)
        self.bubble_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.middle_row_layout.addWidget(self.bubble_label, 0, Qt.AlignLeft)

        # Right-aligned anchor layout space strictly reserved for rendering the pixel cat
        self.cat_canvas_space = QLabel()
        self.cat_canvas_space.setFixedSize(128, 128)
        self.middle_row_layout.addWidget(self.cat_canvas_space, 0, Qt.AlignRight)

        self.main_layout.addLayout(self.middle_row_layout)

        # ─── BOTTOM CONTROL INTERFACE LAYER: ZERO-PADDING COMPACT DECK ───
        self.control_deck_layout = QVBoxLayout()
        self.control_deck_layout.setContentsMargins(0, 0, 0, 0)  # STRIP AWAY PADDING
        self.control_deck_layout.setSpacing(2)  # TIGHT STEP BETWEEN DECK COMPONENTS

        # Model Selector Dropdown
        self.model_selector = QComboBox()
        self.model_selector.addItems(["llama-3.3-70b-versatile", "llama3-8b-8192", "gemini-2.0-flash"])
        self.model_selector.setStyleSheet(
            "background-color: #282c34; color: #61afef; border: 1px solid #4b5263; "
            "border-radius: 3px; font-family: monospace; font-size: 10px; padding: 1px;"
        )
        self.model_selector.setFixedWidth(268)
        self.model_selector.setFixedHeight(20)
        self.control_deck_layout.addWidget(self.model_selector, 0, Qt.AlignCenter)

        # Chat Row Deck input lane
        self.input_row_layout = QHBoxLayout()
        self.input_row_layout.setContentsMargins(0, 0, 0, 0)
        self.input_row_layout.setSpacing(2)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("type to lint...")
        self.chat_input.setStyleSheet(
            "background-color: #1e222b; color: #abb2bf; border: 1px solid #4b5263; "
            "border-radius: 3px; font-family: monospace; font-size: 10px; padding: 2px;"
        )
        self.chat_input.setFixedHeight(20)
        self.chat_input.setFixedWidth(244)
        self.chat_input.returnPressed.connect(self.submit_desktop_chat)

        self.send_btn = QPushButton("👋")
        self.send_btn.setStyleSheet(
            "background-color: #4b5263; color: white; border: none; "
            "border-radius: 3px; font-size: 11px; font-weight: bold;"
        )
        self.send_btn.setFixedSize(22, 20)
        self.send_btn.clicked.connect(self.submit_desktop_chat)

        self.input_row_layout.addWidget(self.chat_input)
        self.input_row_layout.addWidget(self.send_btn)
        self.control_deck_layout.addLayout(self.input_row_layout)

        self.main_layout.addLayout(self.control_deck_layout)

        # Text Fallback node
        self.fallback_canvas = QLabel(" /\\_/\\\n( -.- )\n > ^ <")
        self.fallback_canvas.setStyleSheet(
            "color: #61afef; font-family: monospace; font-size: 14px; font-weight: bold; padding-left: 15px;")
        self.main_layout.addWidget(self.fallback_canvas)
        self.fallback_canvas.hide()

        self.setLayout(self.main_layout)

        # New optimal rigid layout dimension parameters
        self.setFixedSize(276, 178)
        self.move(QApplication.primaryScreen().geometry().width() - 310, 60)

    def submit_desktop_chat(self):
        user_text = self.chat_input.text().strip()
        if not user_text: return

        self.chat_input.clear()
        self.bubble_label.setText("*thinking...*")
        chosen_model = self.model_selector.currentText()
        QTimer.singleShot(0, lambda: self._async_desktop_query(user_text, chosen_model))

    def _async_desktop_query(self, query, model):
        try:
            reply = self.llm.ask_cat(query, model_override=model)
            if reply: self.bubble_label.setText(reply)
        except Exception:
            self.bubble_label.setText("connection error.")

    def passive_chatter(self):
        if not self.isVisible(): return
        chosen_model = self.model_selector.currentText()
        QTimer.singleShot(0, lambda: self._async_talk(chosen_model))

    def _async_talk(self, model):
        try:
            txt = self.llm.ask_cat("make a short single sentence witty comment about a coder typing.",
                                   model_override=model)
            if txt and not txt.startswith("*"): self.bubble_label.setText(txt)
        except:
            pass

    def cycle_frame(self):
        d = self.loaded_sprites.get(self.current_state)
        if not d or d["fallback"]:
            self.fallback_canvas.show()
            return
        self.fallback_canvas.hide()
        self.current_frame = (self.current_frame + 1) % d["total"]
        if self.current_frame == 0 and self.current_state != "default":
            if random.random() < 0.4: self.current_state = "default"
        self.update()

    def paintEvent(self, event):
        d = self.loaded_sprites.get(self.current_state)
        if not d or d["fallback"]: return

        p = QPainter(self)
        src_rect = QRect(self.current_frame * d["w"], 0, d["w"], d["h"])

        space_geometry = self.cat_canvas_space.geometry()
        dest_w = d["w"] * self.sprite_scale
        dest_h = d["h"] * self.sprite_scale

        dest_x = space_geometry.x() + (space_geometry.width() - dest_w) // 2
        dest_y = space_geometry.y() + (space_geometry.height() - dest_h) // 2
        dest_rect = QRect(dest_x, dest_y, dest_w, dest_h)

        p.drawPixmap(dest_rect, d["pixmap"], src_rect)

    def check_lock(self):
        self.hide() if os.path.exists(LOCK_FILE) else self.show()

    def mousePressEvent(self, event):
        # Dragging lock limits restricted exclusively to the active middle row canvas element zone
        if event.y() > 132:
            event.ignore()
            return
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            states = [s for s, data in self.loaded_sprites.items() if not data.get("fallback", True)]
            if states:
                self.current_state = random.choice(states)
                self.current_frame = 0
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.drag_pos.isNull() and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()


def run_gui():
    app = QApplication(sys.argv)
    pet = FloatingCatPet()
    pet.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_gui()