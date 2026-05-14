"""
roblox_background_macro.py
===========================
Non-intrusive background automation for Roblox using Windows API.
Sends inputs directly to the Roblox window without stealing focus.

Dependencies:
    pip install pywin32 keyboard

Build to exe:
    pyinstaller --onefile --console ^
        --hidden-import win32gui ^
        --hidden-import win32api ^
        --hidden-import win32con ^
        roblox_background_macro.py

Hotkeys:
    F3  →  Toggle macro ON / OFF
    F4  →  Exit script
"""

import sys
import time
import threading
import ctypes

import win32gui
import win32api
import win32con
import keyboard

# ============================================================
# ▶  CONFIGURATION
# ============================================================

TARGET_APP_TITLE = "Roblox"   # Matches any window containing "Roblox"

# Timing (seconds)
LOOP_INTERVAL = 0.05    # Main loop tick  (50 ms)
ACTION_DELAY  = 0.02    # Between key-down and key-up
CLICK_DELAY   = 0.015   # Between mouse-down and mouse-up

# Hotkeys
HOTKEY_TOGGLE = "f3"
HOTKEY_EXIT   = "f4"

# ============================================================
# ▶  GLOBAL STATE
# ============================================================

running     = False
_stop_event = threading.Event()


# ============================================================
# ▶  SAFE ALERT (works in exe, no stdin needed)
# ============================================================

def alert(title: str, message: str) -> None:
    """Show a Windows message box — works inside a compiled .exe."""
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR


def info(title: str, message: str) -> None:
    """Show an info message box."""
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)  # MB_ICONINFORMATION


# ============================================================
# ▶  WINDOW FINDER
# ============================================================

def find_window(title_fragment: str) -> int | None:
    """
    Find a visible window whose title contains title_fragment (case-insensitive).
    Returns the HWND or None.
    """
    found = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            if title_fragment.lower() in win32gui.GetWindowText(hwnd).lower():
                found.append(hwnd)

    win32gui.EnumWindows(callback, None)

    if found:
        hwnd  = found[0]
        title = win32gui.GetWindowText(hwnd)
        print(f"[✓] Found  →  HWND={hwnd:#010x}  '{title}'")
        return hwnd

    print(f"[✗] Window not found: '{title_fragment}'")
    return None


def require_window(title_fragment: str) -> int:
    """
    Find the window or show an error popup and exit — safe for compiled .exe.
    """
    hwnd = find_window(title_fragment)
    if hwnd is None:
        alert(
            "Window Not Found",
            f"Could not find a window containing:\n\n\"{title_fragment}\"\n\n"
            "Make sure Roblox is open, then run the macro again."
        )
        sys.exit(1)
    return hwnd


# ============================================================
# ▶  BACKGROUND INPUT — KEYBOARD
# ============================================================

def send_key_background(hwnd: int, vk_code: int) -> None:
    """
    Send a key press (down + up) to hwnd without focusing the window.

    Parameters
    ----------
    hwnd    : target window handle
    vk_code : Virtual-Key code  (e.g. win32con.VK_SPACE, ord('E'), 0x41)
    """
    scan  = ctypes.windll.user32.MapVirtualKeyW(vk_code, 0)
    lp_dn = (scan << 16) | 1
    lp_up = (scan << 16) | 0xC0000001

    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lp_dn)
    time.sleep(ACTION_DELAY)
    win32api.PostMessage(hwnd, win32con.WM_KEYUP,   vk_code, lp_up)


# ============================================================
# ▶  BACKGROUND INPUT — MOUSE
# ============================================================

def _lp(x: int, y: int) -> int:
    return (y << 16) | (x & 0xFFFF)


def click_background(hwnd: int, x: int, y: int) -> None:
    """
    Left-click at client coordinates (x, y) inside hwnd.
    Coordinates are relative to the top-left of the Roblox window.
    """
    lp = _lp(x, y)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
    time.sleep(CLICK_DELAY)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP,   0,                   lp)


def get_client_center(hwnd: int) -> tuple[int, int]:
    r = win32gui.GetClientRect(hwnd)
    return r[2] // 2, r[3] // 2


def screen_to_client(hwnd: int, sx: int, sy: int) -> tuple[int, int]:
    pt = win32gui.ScreenToClient(hwnd, (sx, sy))
    return pt[0], pt[1]


# ============================================================
# ▶  MACRO LOGIC  ← put your Roblox actions here
# ============================================================

def macro_loop(hwnd: int) -> None:
    """
    Main loop running on its own thread.
    Edit the section marked below to add your Roblox actions.
    """
    print("[MACRO] Thread started.")

    while not _stop_event.is_set():

        # ── Paused ──────────────────────────────────────────
        if not running:
            time.sleep(0.1)
            continue

        # ── Window still alive? ──────────────────────────────
        if not win32gui.IsWindow(hwnd):
            print("[!] Roblox window closed — pausing.")
            set_running(False)
            time.sleep(1.0)
            continue

        # ════════════════════════════════════════════════════
        #   YOUR ROBLOX ACTIONS — edit below
        # ════════════════════════════════════════════════════

        # --- Example: Auto-jump (press Space every tick) ---
         send_key_background(hwnd, win32con.VK_SPACE)

        # --- Example: Press 'E' to interact / collect ---
        # send_key_background(hwnd, ord('E'))

        # --- Example: Click center of screen ---
        # cx, cy = get_client_center(hwnd)
        # click_background(hwnd, cx, cy)

        # --- Example: W key (move forward) ---
        # send_key_background(hwnd, ord('W'))

        # ════════════════════════════════════════════════════
        #   END OF YOUR ACTIONS
        # ════════════════════════════════════════════════════

        time.sleep(LOOP_INTERVAL)

    print("[MACRO] Thread exited.")


# ============================================================
# ▶  STATE HELPERS
# ============================================================

def set_running(state: bool) -> None:
    global running
    running = state
    label   = "RUNNING  ▶" if state else "PAUSED   ⏸"
    print(f"\n[STATUS] {label}\n")


def toggle_macro() -> None:
    set_running(not running)


def exit_script() -> None:
    print("\n[EXIT] Shutting down...")
    _stop_event.set()
    keyboard.unhook_all()


# ============================================================
# ▶  ENTRY POINT
# ============================================================

def main() -> None:
    print("=" * 55)
    print("  Roblox Background Macro")
    print(f"  Target : '{TARGET_APP_TITLE}'")
    print(f"  Toggle : {HOTKEY_TOGGLE.upper()}   |   Exit : {HOTKEY_EXIT.upper()}")
    print("=" * 55)

    hwnd = require_window(TARGET_APP_TITLE)

    keyboard.add_hotkey(HOTKEY_TOGGLE, toggle_macro)
    keyboard.add_hotkey(HOTKEY_EXIT,   exit_script)

    print(f"\nReady. Press {HOTKEY_TOGGLE.upper()} to start, {HOTKEY_EXIT.upper()} to exit.\n")

    t = threading.Thread(target=macro_loop, args=(hwnd,), daemon=True, name="MacroLoop")
    t.start()

    _stop_event.wait()   # Block here — no input() call, safe in .exe
    print("[EXIT] Done.")


if __name__ == "__main__":
    main()
