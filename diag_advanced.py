import cv2
import numpy as np
import mss
import json
import win32gui
import os

def is_player_debug(frame, x, y, w, h):
    roi_y_start = max(0, y - 25)
    roi_y_end = y + 5
    roi_x_start = x
    roi_x_end = x + w
    
    name_roi = frame[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
    if name_roi.size == 0: return False, 0, 0
    
    hsv = cv2.cvtColor(name_roi, cv2.COLOR_BGR2HSV)
    mask_blue = cv2.inRange(hsv, np.array([90, 50, 50]), np.array([130, 255, 255]))
    mask_red = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255]))
    
    b_count = cv2.countNonZero(mask_blue)
    r_count = cv2.countNonZero(mask_red)
    
    is_p = b_count > 20 or r_count > 20
    return is_p, b_count, r_count

def run_diag():
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            if "lineage classic" in title:
                windows.append((hwnd, title))
    
    windows = []
    win32gui.EnumWindows(callback, windows)
    if not windows:
        print("[-] Window NOT FOUND")
        return

    hwnd, title = windows[0]
    rect = win32gui.GetWindowRect(hwnd)
    print(f"[+] Window Found: {title} at {rect}")
    
    with mss.mss() as sct:
        monitor = {"top": rect[1], "left": rect[0], "width": rect[2]-rect[0], "height": rect[3]-rect[1]}
        img = np.array(sct.grab(monitor))
        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        debug_frame = frame.copy()

        # Test Motion Detection Simulation (Static for now)
        # Background Masking Test
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask_bg = cv2.inRange(hsv, np.array([10, 20, 20]), np.array([85, 255, 200]))
        mask_inv = cv2.bitwise_not(mask_bg)
        cnts, _ = cv2.findContours(mask_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        found_any = False
        for c in cnts:
            if 300 < cv2.contourArea(c) < 5000:
                x, y, w, h = cv2.boundingRect(c)
                is_p, b, r = is_player_debug(frame, x, y, w, h)
                
                # Update: Player decision threshold to 30 for debug consistency
                is_p = b > 30 or r > 30
                label = f"PLAYER (B:{b} R:{r})" if is_p else "TARGET"
                cv2.rectangle(debug_frame, (x, y), (x+w, y+h), color, 2)
                cv2.putText(debug_frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                found_any = True
                print(f"[*] Blob at ({x},{y}): {label}")

        if not found_any:
            print("[-] No potential entities found in base masking.")
            
        os.makedirs('docs', exist_ok=True)
        cv2.imwrite('docs/advanced_diag.png', debug_frame)
        print("[+] Diagnostic image saved to docs/advanced_diag.png")

if __name__ == "__main__":
    run_diag()
