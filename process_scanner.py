import psutil
import win32gui
import win32process
import os

def get_window_titles():
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    process = psutil.Process(pid)
                    windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "pid": pid,
                        "name": process.name()
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    windows = []
    win32gui.EnumWindows(callback, windows)
    return windows

if __name__ == "__main__":
    print("Mapping active windows to processes...")
    try:
        windows = get_window_titles()
        found = False
        for w in windows:
            # Filter for game-related terms
            search_terms = ["lineage", "nc", "classic", "l1"]
            if any(term in w["title"].lower() or term in w["name"].lower() for term in search_terms):
                print(f"[*] POTENTIAL MATCH: [{w['name']}] (PID: {w['pid']}) -> '{w['title']}'")
                found = True
        
        if not found:
            print("[!] No obvious 'Lineage' process found. Listing ALL windows with titles:")
            for w in windows:
                print(f"  [{w['name']}] (PID: {w['pid']}) -> '{w['title']}'")
    except Exception as e:
        print(f"Error: {e}")
