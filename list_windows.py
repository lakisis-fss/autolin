import win32gui

def callback(hwnd, extra):
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if "Lineage" in title:
            print(f"HWND: {hwnd}, Title: {title}")

if __name__ == "__main__":
    win32gui.EnumWindows(callback, None)
