"""
background_macro.py
====================
Non-intrusive background automation using Windows API (User32 via pywin32).
Sends keyboard/mouse inputs directly to a target window without stealing focus.

Dependencies:
    pip install pywin32 keyboard

Usage:
    1. Set TARGET_APP_TITLE to the window title of your game/app.
    2. Run the script.
    3. Press F3 to toggle ON/OFF.
    4. Press F4 to exit cleanly.
"""

import time
import threading
import ctypes

import win32gui
import win32api
import win32con
import keyboard  # pip install keyboard

# ============================================================
# ▶  CONFIGURATION — edit these to match your target app
# ============================================================

TARGET_APP_TITLE = "Your Application Title Here"  # Partial or full window title

# Fixed timing values (in seconds) — adjust to match your game's rhythm
LOOP_INTERVAL   = 0.05   # How often the main loop ticks  (50 ms)
ACTION_DELAY    = 0.02   # Pause between key-down and key-up inside send_key
CLICK_DELAY     = 0.015  # Pause between button-down and button-up inside click

# Hotkeys
HOTKEY_TOGGLE   = "f3"   # Press to start / pause the macro
HOTKEY_EXIT     = "f4"   # Press to exit the script entirely

# ============================================================
# ▶  GLOBAL STATE
# ============================================================

running       = False   # Macro active flag
_stop_event   = threading.Event()


# ============================================================
# ▶  WINDOW FINDER
# ============================================================

def find_window(title_fragment: str) -> int | None:
    """
    Search for a visible window whose title contains `title_fragment`
    (case-insensitive).  Returns the HWND or None if not found.
    """
    found_hwnd = []

    def enum_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            wnd_title = win32gui.GetWindowText(hwnd)
            if title_fragment.lower() in wnd_title.lower():
                found_hwnd.append(hwnd)

    win32gui.EnumWindows(enum_callback, None)

    if found_hwnd:
        hwnd = found_hwnd[0]
        title = win32gui.GetWindowText(hwnd)
        print(f"[✓] Window found  →  HWND={hwnd:#010x}  Title='{title}'")
        return hwnd

    print(f"[✗] Window NOT found: '{title_fragment}'")
    print("    Make sure the application is open and the title is correct.")
    return None


def require_window(title_fragment: str) -> int:
    """Like find_window but exits the script if the window is missing."""
    hwnd = find_window(title_fragment)
    if hwnd is None:
        input("\nPress Enter to exit...")
        raise SystemExit(1)
    return hwnd


# ============================================================
# ▶  BACKGROUND INPUT — KEYBOARD
# ============================================================

def send_key_background(hwnd: int, vk_code: int) -> None:
    """
    Send a single key press (down + up) to `hwnd` in the background.

    Parameters
    ----------
    hwnd    : target window handle
    vk_code : Virtual-Key code (e.g. win32con.VK_SPACE, ord('A'), 0x41)

    Uses PostMessage (fire-and-forget) so the script never blocks
    waiting for the target app to process the message.
    """
    # WM_KEYDOWN  — lParam bits: repeat=1, scancode, extended, etc.
    scan_code = ctypes.windll.user32.MapVirtualKeyW(vk_code, 0)
    lp_down   = (scan_code << 16) | 1            # repeat count = 1
    lp_up     = (scan_code << 16) | 0xC0000001   # transition + previous state flags

    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, lp_down)
    time.sleep(ACTION_DELAY)
    win32api.PostMessage(hwnd, win32con.WM_KEYUP,   vk_code, lp_up)


def send_char_background(hwnd: int, char: str) -> None:
    """
    Send a WM_CHAR message for text-input fields.
    Use this for typing characters; use send_key_background for control keys.
    """
    win32api.PostMessage(hwnd, win32con.WM_CHAR, ord(char), 0)


# ============================================================
# ▶  BACKGROUND INPUT — MOUSE
# ============================================================

def _make_lparam(x: int, y: int) -> int:
    """Pack (x, y) client coordinates into a single LPARAM value."""
    return (y << 16) | (x & 0xFFFF)


def click_background(hwnd: int, x: int, y: int) -> None:
    """
    Send a left mouse click to `hwnd` at CLIENT coordinates (x, y).

    Client coordinates are relative to the top-left corner of the
    target window's client area — NOT screen coordinates.

    Parameters
    ----------
    hwnd : target window handle
    x, y : position in client (window-relative) coordinates
    """
    lp = _make_lparam(x, y)

    win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
    time.sleep(CLICK_DELAY)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP,   0,                   lp)


def right_click_background(hwnd: int, x: int, y: int) -> None:
    """Same as click_background but for the right mouse button."""
    lp = _make_lparam(x, y)
    win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, lp)
    time.sleep(CLICK_DELAY)
    win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP,   0,                   lp)


def move_mouse_background(hwnd: int, x: int, y: int) -> None:
    """Send a WM_MOUSEMOVE to `hwnd` at client coordinates (x, y)."""
    win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, _make_lparam(x, y))


# ============================================================
# ▶  COORDINATE HELPERS
# ============================================================

def screen_to_client(hwnd: int, screen_x: int, screen_y: int) -> tuple[int, int]:
    """Convert screen (absolute) coordinates to client coordinates for `hwnd`."""
    pt = win32gui.ScreenToClient(hwnd, (screen_x, screen_y))
    return pt[0], pt[1]


def get_client_center(hwnd: int) -> tuple[int, int]:
    """Return the center point of the window's client area."""
    rect = win32gui.GetClientRect(hwnd)          # (left, top, right, bottom)
    return rect[2] // 2, rect[3] // 2


# ============================================================
# ▶  MACRO LOGIC  ← customise everything inside here
# ============================================================

def macro_loop(hwnd: int) -> None:
    """
    Main macro loop — runs on its own thread while the macro is RUNNING.

    Replace the example actions below with whatever your automation needs.
    The loop stops when running becomes False or _stop_event is set.
    """
    print("[MACRO] Loop started.")

    while not _stop_event.is_set():

        # ── Wait if paused ──────────────────────────────────────
        if not running:
            time.sleep(0.1)
            continue

        # ── Re-validate window (may have closed/re-opened) ──────
        if not win32gui.IsWindow(hwnd):
            print("[!] Target window closed. Pausing macro.")
            set_running(False)
            time.sleep(1.0)
            continue

        # ════════════════════════════════════════════════════════
        #   YOUR AUTOMATION ACTIONS GO HERE
        #   Examples shown below — replace with your own logic.
        # ════════════════════════════════════════════════════════

        # Example 1: Press SPACE every loop tick
        # send_key_background(hwnd, win32con.VK_SPACE)

        # Example 2: Click at a fixed position in the client area
        # click_background(hwnd, x=400, y=300)

        # Example 3: Press a letter key  (ord gives the VK code for A-Z)
        # send_key_background(hwnd, ord('E'))

        # Example 4: Click the center of the window
        # cx, cy = get_client_center(hwnd)
        # click_background(hwnd, cx, cy)

        # ────────────────────────────────────────────────────────
        #   END OF YOUR ACTIONS
        # ────────────────────────────────────────────────────────

        time.sleep(LOOP_INTERVAL)

    print("[MACRO] Loop exited.")


# ============================================================
# ▶  STATE MANAGEMENT
# ============================================================

_macro_thread: threading.Thread | None = None

def set_running(state: bool) -> None:
    """Toggle the macro on or off and print a status message."""
    global running
    running = state
    label = "RUNNING  ▶" if state else "PAUSED   ⏸"
    print(f"\n[STATUS] {label}\n")


def toggle_macro() -> None:
    """Called when the toggle hotkey is pressed."""
    set_running(not running)


def exit_script() -> None:
    """Called when the exit hotkey is pressed."""
    print("\n[EXIT] Shutting down...")
    _stop_event.set()
    keyboard.unhook_all()


# ============================================================
# ▶  ENTRY POINT
# ============================================================

def main() -> None:
    global _macro_thread

    print("=" * 55)
    print("  Background Macro — pywin32 edition")
    print(f"  Target : '{TARGET_APP_TITLE}'")
    print(f"  Toggle : {HOTKEY_TOGGLE.upper()}")
    print(f"  Exit   : {HOTKEY_EXIT.upper()}")
    print("=" * 55)

    # ── Locate the target window ────────────────────────────
    hwnd = require_window(TARGET_APP_TITLE)

    # ── Register global hotkeys ─────────────────────────────
    keyboard.add_hotkey(HOTKEY_TOGGLE, toggle_macro)
    keyboard.add_hotkey(HOTKEY_EXIT,   exit_script)

    print(f"\nReady. Press {HOTKEY_TOGGLE.upper()} to start the macro.")
    print(f"Press {HOTKEY_EXIT.upper()} to exit.\n")

    # ── Start the macro thread ──────────────────────────────
    _macro_thread = threading.Thread(
        target=macro_loop,
        args=(hwnd,),
        daemon=True,
        name="MacroLoop",
    )
    _macro_thread.start()

    # ── Block main thread until exit hotkey fires ───────────
    _stop_event.wait()
    print("[EXIT] Done.")


if __name__ == "__main__":
    main()
