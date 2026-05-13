import cv2
import numpy as np
import mss
import json
import win32gui
import os

def diag():
    # 1. Find Window
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "Lineage Classic" in title:
                windows.append((hwnd, title))
    
    windows = []
    win32gui.EnumWindows(callback, windows)
    
    if not windows:
        print("[-] Lineage Classic window NOT FOUND.")
        return
    
    hwnd, title = windows[0]
    print(f"[+] Found Window: {title} (HWND: {hwnd})")
    
    # 2. Capture
    rect = win32gui.GetWindowRect(hwnd)
    monitor = {"top": rect[1], "left": rect[0], "width": rect[2]-rect[0], "height": rect[3]-rect[1]}
    
    with mss.mss() as sct:
        sct_img = sct.grab(monitor)
        frame = np.array(sct_img)
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        
        # Check if black
        if np.all(frame_bgr == 0):
            print("[-] CRITICAL: Captured image is ALL BLACK. Anti-cheat might be blocking mss.")
        else:
            print("[+] Capture SUCCESS: Image data detected.")
            
        # Save for manual check
        os.makedirs('docs', exist_ok=True)
        cv2.imwrite('docs/engine_diag_capture.png', frame_bgr)
        print("[+] Debug image saved to docs/engine_diag_capture.png")

    # 3. Test Matching
    mapping_path = 'resources/monster_mapping.json'
    if os.path.exists(mapping_path):
        mapping = json.load(open(mapping_path, 'r', encoding='utf-8'))
        # Try matching first few
        for name, path in list(mapping.items())[:5]:
            template = cv2.imread(path)
            if template is not None:
                res = cv2.matchTemplate(frame_bgr, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                print(f"[*] Match Test - {name}: Confidence = {max_val:.4f}")

if __name__ == "__main__":
    diag()
