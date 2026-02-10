import sys
import os
import json
import re
import requests
import pygame
import platform
import subprocess
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QScrollArea, QGridLayout, QLabel,
    QComboBox, QSlider, QMenu, QInputDialog, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtGui import QCursor, QFontMetrics


CONFIG_FILE = "config.json"
SOUNDS_DIR = "my_memes"
VIRTUAL_SINK_NAME = "MemeBoard_Virtual_Output"
VIRTUAL_REMAP_NAME = "Virtual_Mic_Remap"

try:
    import pygame._sdl2.audio as sdl2_audio
    HAS_SDL2 = True
except ImportError:
    HAS_SDL2 = False

class DownloadWorker(QObject):
    finished = Signal(str, str)
    error = Signal(str)

    def run(self, url):
        try:
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            m = re.search(r'https?://[^\s"\']+\.mp3', r.text)
            if m:
                mp3_url = m.group(0)
                t = re.search(r'<title>(.*?)</title>', r.text, re.I)
                name = re.sub(r'(?i)Sound Button|MyInstants|Download|Mp3|Online|<.*?>', '', t.group(1) if t else "Sound").strip().title()
                name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
                if not name:
                    name = "Unnamed_Sound"
                path = os.path.join(SOUNDS_DIR, f"{name}.mp3")
                with open(path, 'wb') as f:
                    f.write(requests.get(mp3_url).content)
                self.finished.emit(name, path)
            else:
                self.error.emit("No MP3 found.")
        except Exception as e:
            self.error.emit(str(e))

class ModernMemeBoard(QMainWindow):
    download_requested = Signal(str)

    special_key_map = {
        Qt.Key_Space: "space",
        Qt.Key_Enter: "enter",
        Qt.Key_Return: "enter",
        Qt.Key_Escape: "esc",
        Qt.Key_Backspace: "backspace",
        Qt.Key_Delete: "delete",
        Qt.Key_Tab: "tab",
        Qt.Key_Left: "left",
        Qt.Key_Right: "right",
        Qt.Key_Up: "up",
        Qt.Key_Down: "down",
        Qt.Key_Home: "home",
        Qt.Key_End: "end",
        Qt.Key_PageUp: "pageup",
        Qt.Key_PageDown: "pagedown",
        Qt.Key_Insert: "insert",
        Qt.Key_F1: "f1",
        Qt.Key_F2: "f2",
        Qt.Key_F3: "f3",
        Qt.Key_F4: "f4",
        Qt.Key_F5: "f5",
        Qt.Key_F6: "f6",
        Qt.Key_F7: "f7",
        Qt.Key_F8: "f8",
        Qt.Key_F9: "f9",
        Qt.Key_F10: "f10",
        Qt.Key_F11: "f11",
        Qt.Key_F12: "f12",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MemeBoard v1 by HoppouSan")
        self.resize(1150, 850)

        os.makedirs(SOUNDS_DIR, exist_ok=True)

        pygame.init()
        pygame.mixer.init()

        self.config = self.load_config()
        self.favorites = self.config.get("favorites", [])
        self.hotkeys = self.config.get("hotkeys", {})
        self.categories = self.config.get("categories", ["All", "Uncategorized"])
        self.sound_to_cat = self.config.get("sound_to_cat", {})

        self.buttons_data = []
        self.active_category = "All"
        self.current_volume = self.config.get("volume", 0.7)
        self.mic_volume = self.config.get("mic_volume", 100)  # 0–200%
        self.send_to_chat = False  

        self.setup_ui()
        self.apply_styles()

        if platform.system() == "Linux":
            self.ensure_virtual_audio()
            self.apply_mic_volume()

        self.load_sounds()
        self.apply_volume_to_all()

        self.dl_thread = QThread()
        self.worker = DownloadWorker()
        self.worker.moveToThread(self.dl_thread)
        self.download_requested.connect(self.worker.run)
        self.worker.finished.connect(self.on_dl_success)
        self.worker.error.connect(self.on_dl_error)
        self.dl_thread.start()

    def closeEvent(self, event):
        self.config["volume"] = self.current_volume
        self.config["mic_volume"] = self.mic_volume
        self.save_config()
        self.dl_thread.quit()
        self.dl_thread.wait()
        super().closeEvent(event)

    def ensure_virtual_audio(self):
        if not HAS_SDL2:
            return

        try:
            sinks = subprocess.check_output(["pactl", "list", "short", "sinks"], text=True)
            if VIRTUAL_SINK_NAME not in sinks:
                subprocess.check_call([
                    "pactl", "load-module", "module-null-sink",
                    f"sink_name={VIRTUAL_SINK_NAME}",
                    f"sink_properties=device.description={VIRTUAL_SINK_NAME}"
                ])
                time.sleep(2)

            sources = subprocess.check_output(["pactl", "list", "short", "sources"], text=True)
            if VIRTUAL_REMAP_NAME not in sources:
                subprocess.check_call([
                    "pactl", "load-module", "module-remap-source",
                    f"master={VIRTUAL_SINK_NAME}.monitor",
                    f"source_name={VIRTUAL_REMAP_NAME}",
                    f"source_properties=device.description=Virtual_Mic_{VIRTUAL_SINK_NAME}"
                ])
                time.sleep(2)

                QMessageBox.information(self, "Virtual Microphone Created",
                    "Virtual cable and microphone created.\n\n"
                    "How to use:\n"
                    "• Default (button OFF): Sounds play over your speakers/headset\n"
                    "• Turn 'Send to Voice Chat' ON: Sounds go into virtual mic (for Discord/Zoom)\n"
                    "• In Discord → Input Device → 'Virtual_Mic_Remap'\n\n"
                    "Test: Turn ON → play sound → mic levels should move in Discord.")

            outputs = self.get_output_devices()
            self.output_combo.clear()
            self.output_combo.addItems(outputs)
            self.output_combo.setCurrentIndex(0)
            self.change_output_device(0)  

            self.virtual_input_combo.clear()
            self.virtual_input_combo.addItem(f"Virtual_Mic_{VIRTUAL_SINK_NAME}")
            self.virtual_input_combo.addItem("(set in Discord/Zoom)")
            self.virtual_input_combo.setCurrentIndex(0)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Virtual audio setup failed: {e}")

    def get_output_devices(self):
        return sdl2_audio.get_audio_device_names(False) if HAS_SDL2 else ["System Default"]

    def change_output_device(self, index):
        if not HAS_SDL2:
            return
        
        dev = VIRTUAL_SINK_NAME if self.send_to_chat else self.output_combo.itemText(index)
        try:
            pygame.mixer.quit()
            pygame.mixer.init(devicename=dev)
            self.apply_volume_to_all()
        except pygame.error as e:
            QMessageBox.warning(self, "Audio Error", f"Cannot use device '{dev}':\n{e}\nFalling back to default.")

            pygame.mixer.quit()
            pygame.mixer.init()

    def toggle_send_to_chat(self, checked):
        self.send_to_chat = checked
        self.change_output_device(self.output_combo.currentIndex())
        self.send_to_chat_btn.setText("Send to Voice Chat: ON" if checked else "Send to Voice Chat: OFF")
        self.send_to_chat_btn.setStyleSheet(
            "background:#4caf50; color:white; font-weight:bold;" if checked else ""
        )

    def apply_volume_to_all(self):
        for item in self.buttons_data:
            item["sound"].set_volume(self.current_volume)

    def apply_mic_volume(self):
        if platform.system() != "Linux":
            return
        try:
            subprocess.run([
                "pactl", "set-source-volume", VIRTUAL_REMAP_NAME,
                f"{self.mic_volume}%"
            ], check=True)
        except Exception as e:
            print(f"Mic volume error: {e}")

    def set_vol(self, value):
        self.current_volume = value / 100.0
        self.apply_volume_to_all()

    def set_mic_vol(self, value):
        self.mic_volume = value
        self.mic_vol_label.setText(f"{value}%")
        self.apply_mic_volume()

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return

        mods = event.modifiers()
        if mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
            super().keyPressEvent(event)
            return

        key_int = event.key()
        name = self.special_key_map.get(key_int)

        if name is None:
            text = event.text()
            if text:
                name = text.lower()

        if name == "space":
            pygame.mixer.stop()
        else:
            target_lower = self.hotkeys.get(name)
            if target_lower:
                for it in self.buttons_data:
                    if it["name"] == target_lower:
                        it["sound"].play()
                        break

        event.accept()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"favorites": [], "hotkeys": {}, "categories": ["All", "Uncategorized"], "sound_to_cat": {}, "volume": 0.7, "mic_volume": 100}

    def save_config(self):
        data = {
            "favorites": self.favorites,
            "hotkeys": self.hotkeys,
            "categories": self.categories,
            "sound_to_cat": self.sound_to_cat,
            "volume": self.current_volume,
            "mic_volume": self.mic_volume
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)


        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(top_bar)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste link & right-click for menu...")
        self.url_input.setContextMenuPolicy(Qt.CustomContextMenu)
        self.url_input.customContextMenuRequested.connect(self.show_url_context_menu)
        self.dl_btn = QPushButton("Add")
        self.dl_btn.setObjectName("DownloadBtn")
        self.dl_btn.clicked.connect(self.start_dl)
        top_layout.addWidget(QLabel("🎙️ MEMEBOARD"))
        top_layout.addWidget(self.url_input)
        top_layout.addWidget(self.dl_btn)
        layout.addWidget(top_bar)


        cat_section = QFrame()
        cat_section.setObjectName("CatFrame")
        cat_ribbon_layout = QHBoxLayout(cat_section)
        self.cat_layout = QHBoxLayout()
        cat_ribbon_layout.addLayout(self.cat_layout)

        self.add_cat_btn = QPushButton("+")
        self.add_cat_btn.setFixedSize(30, 30)
        self.add_cat_btn.setObjectName("CatControlBtn")
        self.add_cat_btn.clicked.connect(self.add_cat_dialog)

        self.del_cat_btn = QPushButton("🗑️")
        self.del_cat_btn.setFixedSize(30, 30)
        self.del_cat_btn.setObjectName("CatControlBtnDelete")
        self.del_cat_btn.clicked.connect(self.delete_active_category)

        cat_ribbon_layout.addStretch()
        cat_ribbon_layout.addWidget(self.add_cat_btn)
        cat_ribbon_layout.addWidget(self.del_cat_btn)
        layout.addWidget(cat_section)


        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setFrameShape(QFrame.NoFrame)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_scroll.setWidget(self.grid_container)
        layout.addWidget(self.grid_scroll)

        # Footer
        footer = QFrame()
        footer.setObjectName("Footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 10, 12, 10)
        footer_layout.setSpacing(12)

        footer_layout.addWidget(QLabel("Output (hear):"))
        self.output_combo = QComboBox()
        self.output_combo.setFixedWidth(220)
        footer_layout.addWidget(self.output_combo)

        self.send_to_chat_btn = QPushButton("Send to Voice Chat: OFF")
        self.send_to_chat_btn.setCheckable(True)
        self.send_to_chat_btn.toggled.connect(self.toggle_send_to_chat)
        footer_layout.addWidget(self.send_to_chat_btn)

        footer_layout.addStretch(1)

        self.stop_btn = QPushButton("🛑 STOP ALL (SPACE)")
        self.stop_btn.setObjectName("StopBtn")
        self.stop_btn.setMinimumWidth(180)
        self.stop_btn.clicked.connect(pygame.mixer.stop)
        footer_layout.addWidget(self.stop_btn)

        footer_layout.addStretch(1)

        footer_layout.addWidget(QLabel("Virtual Mic:"))
        self.virtual_input_combo = QComboBox()
        self.virtual_input_combo.setFixedWidth(220)
        self.virtual_input_combo.setEnabled(False)
        footer_layout.addWidget(self.virtual_input_combo)

        footer_layout.addStretch(1)

        footer_layout.addWidget(QLabel("Vol:"))
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(self.current_volume * 100))
        self.vol_slider.setFixedWidth(140)
        self.vol_slider.valueChanged.connect(self.set_vol)
        footer_layout.addWidget(self.vol_slider)

        footer_layout.addWidget(QLabel("Mic Vol:"))
        self.mic_vol_slider = QSlider(Qt.Horizontal)
        self.mic_vol_slider.setRange(0, 200)
        self.mic_vol_slider.setValue(self.mic_volume)
        self.mic_vol_slider.setFixedWidth(140)
        self.mic_vol_slider.valueChanged.connect(self.set_mic_vol)
        footer_layout.addWidget(self.mic_vol_slider)

        self.mic_vol_label = QLabel(f"{self.mic_volume}%")
        self.mic_vol_label.setFixedWidth(50)
        footer_layout.addWidget(self.mic_vol_label)

        footer_layout.addStretch(1)

        self.on_top_btn = QPushButton("📌 Always on Top: OFF")
        self.on_top_btn.setCheckable(True)
        self.on_top_btn.toggled.connect(self.toggle_on_top)
        footer_layout.addWidget(self.on_top_btn)

        layout.addWidget(footer)

        self.render_cats()

    def toggle_on_top(self, checked):
        flags = self.windowFlags()
        if checked:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
            self.on_top_btn.setText("📌 Always on Top: ON")
            self.on_top_btn.setStyleSheet("background:#90ee90;color:black;font-weight:bold;")
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
            self.on_top_btn.setText("📌 Always on Top: OFF")
            self.on_top_btn.setStyleSheet("")
        self.show()

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0f0f13; }
            #TopBar { background-color: #16161e; border-bottom: 1px solid #25252e; padding: 12px; }
            #CatFrame { background-color: #16161e; border-bottom: 1px solid #25252e; padding: 5px 15px; }
            #Footer { background-color: #16161e; border-top: 1px solid #25252e; padding: 10px; }

            QLineEdit { background-color: #09090b; border: 1px solid #333; padding: 10px; border-radius: 8px; color: #ececec; }
            QPushButton#DownloadBtn { background-color: #7289da; color: white; border-radius: 8px; padding: 10px 20px; font-weight: bold; }
            QPushButton#StopBtn { background-color: #e74c3c; color: white; border-radius: 10px; padding: 12px 40px; font-weight: bold; font-size: 15px; }

            QPushButton[btnType="sound"] {
                background-color: #1c1c27; color: #ececec; border: 1px solid #2d2d3d;
                border-radius: 12px; font-size: 13px; font-weight: bold; text-align: center;
            }
            QPushButton[btnType="sound"]:hover { background-color: #252535; border-color: #7289da; }
            QPushButton[btnType="sound"][favorite="true"] { border: 2px solid #f1c40f; background-color: #1e1d15; }

            QPushButton[btnType="cat"] { background-color: transparent; color: #8e8e93; border-radius: 15px; padding: 6px 15px; font-weight: bold; }
            QPushButton[btnType="cat"][active="true"] { background-color: #2d2d3d; color: #7289da; }

            QMenu { background-color: #1c1c27; color: white; border: 1px solid #2d2d3d; }
            QMenu::item:selected { background-color: #7289da; }
            QComboBox { background-color: #09090b; border: 1px solid #333; padding: 8px; border-radius: 6px; }
        """)

    def render_cats(self):
        while self.cat_layout.count():
            w = self.cat_layout.takeAt(0).widget()
            if w:
                w.setParent(None)
        for c in self.categories:
            b = QPushButton(c)
            b.setProperty("btnType", "cat")
            b.setProperty("active", c == self.active_category)
            b.clicked.connect(lambda _, cat=c: self.switch_cat(cat))
            self.cat_layout.addWidget(b)

    def switch_cat(self, c):
        self.active_category = c
        self.render_cats()
        self.refresh_grid()

    def add_cat_dialog(self):
        n, ok = QInputDialog.getText(self, "Category", "Name:")
        if ok and n and n not in self.categories:
            self.categories.append(n)
            self.save_config()
            self.render_cats()

    def delete_active_category(self):
        if self.active_category in ["All", "Uncategorized"]:
            QMessageBox.information(self, "Note", f"The system category '{self.active_category}' cannot be deleted.")
            return

        confirm = QMessageBox.question(self, "Delete Category",
                                       f"Do you really want to delete the category '{self.active_category}'?\nAll sounds in it will be moved to 'Uncategorized'.",
                                       QMessageBox.Yes | QMessageBox.No)

        if confirm == QMessageBox.Yes:
            for s_name, cat in list(self.sound_to_cat.items()):
                if cat == self.active_category:
                    self.sound_to_cat[s_name] = "Uncategorized"

            self.categories.remove(self.active_category)
            self.active_category = "All"
            self.save_config()
            self.render_cats()
            self.refresh_grid()

    def show_url_context_menu(self, pos):
        menu = QMenu(self)
        p = menu.addAction("📋 Paste")
        p.triggered.connect(self.url_input.paste)
        d = menu.addAction("🚀 Paste & Download")
        d.triggered.connect(lambda: [self.url_input.paste(), self.start_dl()])
        menu.exec(self.url_input.mapToGlobal(pos))

    def show_sound_context_menu(self, pos, item):
        menu = QMenu(self)
        mv = menu.addMenu("📂 Move to...")
        for c in self.categories:
            if c != "All":
                a = mv.addAction(c)
                a.triggered.connect(lambda _, cat=c, n=item["display"]: self.move_sound(n, cat))
        hk = menu.addAction("⌨️ Set Hotkey")
        hk.triggered.connect(lambda: self.set_hk(item["display"]))
        fv = menu.addAction("⭐ Toggle Favorite")
        fv.triggered.connect(lambda: self.toggle_fav(item["display"]))
        menu.addSeparator()
        dl = menu.addAction("🗑️ Delete")
        dl.triggered.connect(lambda: self.delete_snd(item))
        menu.exec(QCursor.pos())

    def start_dl(self):
        u = self.url_input.text().strip()
        if u.startswith("http"):
            self.dl_btn.setEnabled(False)
            self.download_requested.emit(u)

    def on_dl_success(self, n, p):
        self.add_sound_obj(n, p)
        self.url_input.clear()
        self.dl_btn.setEnabled(True)
        self.refresh_grid()

    def on_dl_error(self, e):
        QMessageBox.warning(self, "Error", e)
        self.dl_btn.setEnabled(True)

    def load_sounds(self):
        self.buttons_data.clear()
        if os.path.exists(SOUNDS_DIR):
            for f in sorted(os.listdir(SOUNDS_DIR)):
                if f.lower().endswith(".mp3"):
                    name = f[:-4]
                    path = os.path.join(SOUNDS_DIR, f)
                    self.add_sound_obj(name, path)
        self.refresh_grid()

    def add_sound_obj(self, n, p):
        try:
            s = pygame.mixer.Sound(p)
            s.set_volume(self.current_volume)
            self.buttons_data.append({
                "name": n.lower(),
                "display": n,
                "path": p,
                "sound": s
            })
        except:
            pass

    def refresh_grid(self):
        while self.grid_layout.count():
            w = self.grid_layout.takeAt(0).widget()
            if w:
                w.setParent(None)

        visible = [i for i in self.buttons_data if
                   (self.active_category == "All" or
                    self.sound_to_cat.get(i["display"], "Uncategorized") == self.active_category)]

        visible.sort(key=lambda x: (x["display"] not in self.favorites, x["display"]))

        for i, it in enumerate(visible):
            b = QPushButton()
            b.setFixedSize(190, 95)
            b.setProperty("btnType", "sound")
            b.setProperty("favorite", it["display"] in self.favorites)

            metrics = QFontMetrics(b.font())
            elided_text = metrics.elidedText(it["display"], Qt.TextElideMode.ElideRight, 170)
            b.setText(elided_text)
            b.setToolTip(it["display"])

            b.clicked.connect(lambda _, s=it["sound"]: s.play())
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda pos, x=it: self.show_sound_context_menu(pos, x))
            self.grid_layout.addWidget(b, i // 4, i % 4)

    def move_sound(self, n, c):
        self.sound_to_cat[n] = c
        self.save_config()
        self.refresh_grid()

    def toggle_fav(self, n):
        if n in self.favorites:
            self.favorites.remove(n)
        else:
            self.favorites.append(n)
        self.save_config()
        self.refresh_grid()

    def set_hk(self, n):
        k, ok = QInputDialog.getText(self, "Hotkey", f"Key for {n} (e.g. a, f1, space):")
        if ok and k:
            self.hotkeys[k.lower().strip()] = n.lower()
            self.save_config()

    def delete_snd(self, it):
        if QMessageBox.question(self, "Delete", "Really delete file?") == QMessageBox.Yes:
            try:
                os.remove(it["path"])
                if it["display"] in self.favorites:
                    self.favorites.remove(it["display"])
                self.buttons_data.remove(it)
                self.sound_to_cat.pop(it["display"], None)
                self.save_config()
                self.refresh_grid()
            except:
                pass

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernMemeBoard()
    window.show()
    sys.exit(app.exec())
