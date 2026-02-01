import time
import json
import threading
import os
import pyautogui
from pynput import mouse, keyboard
import customtkinter as ctk
from tkinter import filedialog

# ===============================
# CONFIG
# ===============================
ctk.set_appearance_mode("dark")
APP_VERSION = "1.1.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


KEY_MAP = {
    "win": "winleft",
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "alt_l": "alt",
    "alt_r": "alt",
    "shift": "shift",
    "shift_l": "shift",
    "shift_r": "shift",
    "enter": "enter",
    "tab": "tab",
    "esc": "esc",
    "space": "space",
    "backspace": "backspace",
    "delete": "delete",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "caps_lock": "capslock",
    "f1": "f1",
    "f2": "f2",
    "f3": "f3",
    "f4": "f4",
    "f5": "f5",
    "f6": "f6",
    "f7": "f7",
    "f8": "f8",
    "f9": "f9",
    "f10": "f10",
    "f11": "f11",
    "f12": "f12"
}
DEFAULT_HOTKEYS = {
    "record": "f8",
    "play": "f9",
    "abort": "esc"
}

def load_hotkeys():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_HOTKEYS.copy()

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("hotkeys", DEFAULT_HOTKEYS.copy())


def save_hotkeys(hotkeys):
    data = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    data["hotkeys"] = hotkeys

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
HOTKEYS = load_hotkeys()


# ===============================
# CONFIG DE PASTA (persistente)
# ===============================
def save_config(path):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"macro_path": path}, f)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("macro_path")

MACRO_DIR = load_config() or os.path.join(BASE_DIR, "macros")
os.makedirs(MACRO_DIR, exist_ok=True)

def on_hotkey(key):
    global playing

    if not hotkeys_enabled:
        return

    try:
        pressed = key.char.lower()
    except:
        pressed = str(key).replace("Key.", "").lower()

    if pressed == HOTKEYS["record"]:
        if recording:
            stop_record()
        else:
            start_record()

    elif pressed == HOTKEYS["play"]:
        if not playing:
            play_macro()

    elif pressed == HOTKEYS["abort"]:
        playing = False
        stop_record()
        status.configure(text="⛔ Abortado")

# ===============================
# ESTADO
# ===============================
actions = []
recording = False
mouse_listener = None
keyboard_listener = None
last_time = 0
has_recorded = False
overlay = None
playing = False
hotkeys_enabled = True
active_modifiers = set()
MODIFIERS = {
    "ctrl", "ctrl_l", "ctrl_r",
    "alt", "alt_l", "alt_r",
    "shift", "shift_l", "shift_r",
    "win"
}


# ===============================
# UTIL
# ===============================
def list_macros():
    return [f.replace(".json", "") for f in os.listdir(MACRO_DIR) if f.endswith(".json")]

def refresh_macros():
    macro_select.configure(values=list_macros())
    if list_macros():
        macro_select.set(list_macros()[0])

def is_mouse_over_overlay(x, y):
    if not overlay:
        return False
    ox = overlay.winfo_rootx()
    oy = overlay.winfo_rooty()
    ow = overlay.winfo_width()
    oh = overlay.winfo_height()
    return ox <= x <= ox + ow and oy <= y <= oy + oh

# ===============================
# CALLBACKS (IGNORAM AÇÕES DO APP)
# ===============================
def on_click(x, y, button, pressed):
    global last_time
    if not recording or not pressed:
        return
    if is_mouse_over_overlay(x, y):
        return

    delay = time.time() - last_time
    actions.append({
        "type": "click",
        "x": x,
        "y": y,
        "delay": delay
    })
    last_time = time.time()


def on_press(key):
    global last_time
    if not recording:
        return

    delay = time.time() - last_time

    try:
        k = key.char
    except AttributeError:
        if key == keyboard.Key.cmd:
            k = "win"
        else:
            k = str(key).replace("Key.", "")

    actions.append({
        "type": "key_down",
        "key": k,
        "delay": delay
    })

    last_time = time.time()

def atualizar_label_atalhos():
    texto = (
        "⌨️ Atalhos\n"
        f"{HOTKEYS['record']}  Gravar / Parar\n"
        f"{HOTKEYS['play']}  Executar\n"
        f"{HOTKEYS['abort']} Abortar"
    )
    shortcuts.configure(text=texto)

def mudar_atalho(acao, nova_tecla):
    HOTKEYS[acao] = nova_tecla.upper()
    atualizar_label_atalhos()

def on_abort(key):
    global playing, last_time
    if key == keyboard.Key.esc:
        playing = False
        return False


    try:
        if overlay and overlay.focus_get():
            return
    except:
        pass

    delay = time.time() - last_time
    try:
        k = key.char
    except:
        k = str(key).replace("Key.", "")

    actions.append({
        "type": "key",
        "key": k,
        "delay": delay
    })
    last_time = time.time()
    
def on_release(key):
    global last_time
    if not recording:
        return

    try:
        k = key.char
    except AttributeError:
        if key == keyboard.Key.cmd:
            k = "win"
        else:
            k = str(key).replace("Key.", "")

    actions.append({
        "type": "key_up",
        "key": k,
        "delay": 0
    })


def on_scroll(x, y, dx, dy):
    global last_time
    if not recording:
        return
    if is_mouse_over_overlay(x, y):
        return

    delay = time.time() - last_time
    actions.append({
        "type": "scroll",
        "dx": dx,
        "dy": dy,
        "delay": delay
    })
    last_time = time.time()

# ===============================
# OVERLAY
# ===============================
def show_overlay():
    global overlay
    overlay = ctk.CTkToplevel()

    overlay.attributes("-topmost", True)
    overlay.resizable(False, False)

    frame = ctk.CTkFrame(overlay, corner_radius=15)
    frame.pack(expand=True, fill="both", padx=10, pady=10)

    ctk.CTkLabel(frame, text="🔴 Gravando", font=("Arial", 14, "bold")).pack(pady=(5, 8))

    ctk.CTkButton(frame, text="⏹️ Parar", command=stop_record, height=28).pack(fill="x", pady=3)
    ctk.CTkButton(frame, text="💾 Salvar", command=save_macro, height=28).pack(fill="x", pady=3)

    overlay.update_idletasks()

    w = overlay.winfo_width()
    h = overlay.winfo_height()
    x = overlay.winfo_screenwidth() - w - 20
    y = 20

    overlay.geometry(f"{w}x{h}+{x}+{y}")
    overlay.overrideredirect(True)

# ===============================
# CONTROLES
# ===============================
def start_record():
    global recording, actions, last_time, mouse_listener, keyboard_listener, has_recorded

    app.withdraw()
    show_overlay()

    actions.clear()
    has_recorded = True
    recording = True
    last_time = time.time()

    mouse_listener = mouse.Listener(
        on_click=on_click,
        on_scroll=on_scroll
    )

    keyboard_listener = keyboard.Listener(
        on_press=on_press,
        on_release=on_release
    )

    mouse_listener.start()
    keyboard_listener.start()


def stop_record():
    global recording, mouse_listener, keyboard_listener, overlay
    recording = False

    if mouse_listener:
        mouse_listener.stop()
    if keyboard_listener:
        keyboard_listener.stop()

    if overlay:
        overlay.after(0, overlay.destroy)
        overlay = None


    app.deiconify()
    status.configure(text="⏹️ Gravação parada")

def save_macro():
    if not has_recorded:
        status.configure(text="⚠️ Nada para salvar")
        return

    name = macro_name.get().strip()
    if not name:
        status.configure(text="⚠️ Dê um nome à macro")
        return

    path = os.path.join(MACRO_DIR, f"{name}.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(actions, f, indent=4)

    refresh_macros()
    status.configure(text=f"💾 Macro '{name}' salva")

def play_macro():
    def run():
        global playing, active_modifiers
        playing = True
        active_modifiers.clear()

        abort_listener = keyboard.Listener(on_press=on_abort)
        abort_listener.start()

        selected = macro_select.get()
        if not selected:
            app.after(0, lambda: status.configure(text="⚠️ Selecione uma macro"))
            return

        path = os.path.join(MACRO_DIR, f"{selected}.json")
        if not os.path.exists(path):
            app.after(0, lambda: status.configure(text="❌ Macro não existe"))
            return

        with open(path, encoding="utf-8") as f:
            acts = json.load(f)

        for a in acts:
            if not playing:
                break

            time.sleep(max(a["delay"], 0.03))

            if a["type"] == "click":
                pyautogui.click(a["x"], a["y"])

            elif a["type"] == "scroll":
                pyautogui.scroll(a["dy"] * 100)

            elif a["type"] == "key_down":
                key = a["key"].lower()
                mapped = KEY_MAP.get(key, key)

                if key in MODIFIERS:
                    active_modifiers.add(key)
                    pyautogui.keyDown(mapped)
                else:
                    if active_modifiers:
                        # ATALHO
                        pyautogui.keyDown(mapped)
                    else:
                        # TEXTO
                        pyautogui.press(mapped)

            elif a["type"] == "key_up":
                key = a["key"].lower()
                mapped = KEY_MAP.get(key, key)

                pyautogui.keyUp(mapped)
                active_modifiers.discard(key)

        playing = False
        abort_listener.stop()

        # garante limpeza
        for k in ["alt", "ctrl", "shift", "winleft"]:
            pyautogui.keyUp(k)

        app.after(0, lambda: status.configure(text="✅ Macro finalizada"))

    threading.Thread(target=run, daemon=True).start()
def delete_macro():
    selected = macro_select.get()
    if not selected:
        status.configure(text="⚠️ Nenhuma macro selecionada")
        return

    path = os.path.join(MACRO_DIR, f"{selected}.json")
    if not os.path.exists(path):
        status.configure(text="❌ Macro não encontrada")
        return

    os.remove(path)
    refresh_macros()
    status.configure(text=f"🗑 Macro '{selected}' excluída")

# ===============================
# ESCOLHER PASTA
# ===============================
def choose_macro_folder():
    global MACRO_DIR
    path = filedialog.askdirectory(title="Escolha a pasta dos macros")
    if not path:
        return

    MACRO_DIR = path
    os.makedirs(MACRO_DIR, exist_ok=True)
    save_config(path)
    refresh_macros()
    status.configure(text=f"📂 Pasta selecionada")

# ===============================
# GUI PRINCIPAL
# ===============================
# ===============================
# GUI PRINCIPAL
# ===============================
def open_settings():
    win = ctk.CTkToplevel(app)
    win.title("Configurações")
    win.geometry("320x300")
    win.resizable(False, False)
    win.grab_set()

    ctk.CTkLabel(win, text="⌨️ Atalhos do Programa", font=("Arial", 14, "bold")).pack(pady=10)

    entries = {}

    def add_field(label, key):
        frame = ctk.CTkFrame(win, fg_color="transparent")
        frame.pack(pady=6, padx=20, fill="x")

        ctk.CTkLabel(frame, text=label, width=120, anchor="w").pack(side="left")
        e = ctk.CTkEntry(frame, width=100)
        e.insert(0, HOTKEYS[key])
        e.pack(side="right")
        entries[key] = e

    add_field("Gravar / Parar", "record")
    add_field("Executar macro", "play")
    add_field("Abortar", "abort")

    def save():
        for k, e in entries.items():
            HOTKEYS[k] = e.get().lower()

        save_hotkeys(HOTKEYS)

        atualizar_label_atalhos()  # 👈 AQUI ESTÁ A CHAVE

        status.configure(text="⚙️ Atalhos atualizados")
        win.destroy()


    ctk.CTkButton(win, text="💾 Salvar", command=save).pack(pady=15)

app = ctk.CTk()
app.geometry("420x420")
app.title("neXt4")

status = ctk.CTkLabel(app, text="Pronto")
status.pack(pady=8)

# ===============================
# BLOCO DE GRAVAÇÃO
# ===============================
macro_name = ctk.CTkEntry(app, placeholder_text="Nome da macro")
macro_name.pack(pady=6, fill="x", padx=40)

record_frame = ctk.CTkFrame(app, fg_color="transparent")
record_frame.pack(pady=4)

ctk.CTkButton(record_frame, text="🔴 Gravar", command=start_record, width=120).pack(side="left", padx=6)
ctk.CTkButton(record_frame, text="💾 Salvar", command=save_macro, width=120).pack(side="left", padx=6)

# ===============================
# BLOCO DE MACROS
# ===============================
ctk.CTkLabel(app, text="Macros", font=("Arial", 13, "bold")).pack(pady=(12, 4))

macro_select = ctk.CTkComboBox(app, values=list_macros())
macro_select.pack(pady=4, fill="x", padx=40)

macro_action_frame = ctk.CTkFrame(app, fg_color="transparent")
macro_action_frame.pack(pady=6)

ctk.CTkButton(
    macro_action_frame,
    text="▶ Executar",
    command=play_macro,
    width=120
).pack(side="left", padx=6)

ctk.CTkButton(
    macro_action_frame,
    text="🗑 Excluir",
    command=delete_macro,
    width=120
).pack(side="left", padx=6)
ctk.CTkButton(
    app,
    text="⚙️ Configurações",
    command=open_settings
).pack(pady=6)

# ===============================
# CONFIGURAÇÕES
# ===============================
ctk.CTkButton(
    app,
    text="📂 Pasta dos macros",
    command=choose_macro_folder
).pack(pady=10)

# ===============================
# ATALHOS (RESUMIDO)
# ===============================

shortcuts = ctk.CTkLabel(
    app,
    text="",
    justify="left"
)
shortcuts.pack(pady=10)

atualizar_label_atalhos()  # ✅ agora existe

refresh_macros()
keyboard.Listener(on_press=on_hotkey).start()
app.mainloop()

