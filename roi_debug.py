import cv2
import numpy as np
import mss
import win32gui
import os

def get_lineage_rect():
    hwnd_list = []
    def enum_cb(hwnd, results):
        text = win32gui.GetWindowText(hwnd)
        if "Lineage" in text and "Chrome" not in text:
            results.append(hwnd)
    win32gui.EnumWindows(enum_cb, hwnd_list)
    if hwnd_list:
        return win32gui.GetWindowRect(hwnd_list[0])
    return None

rect = get_lineage_rect()
if rect:
    print(f"Rect found: {rect}")
    with mss.mss() as sct:
        monitor = {"top": rect[1], "left": rect[0], "width": rect[2]-rect[0], "height": rect[3]-rect[1]}
        img = np.array(sct.grab(monitor))
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        rois = {
            "hp": {"x": 286, "y": 781, "w": 280, "h": 31},
            "mp": {"x": 622, "y": 781, "w": 280, "h": 31},
            "weight": {"x": 38, "y": 878, "w": 105, "h": 16}
        }
        
        for name, r in rois.items():
            cv2.rectangle(img, (r["x"], r["y"]), (r["x"]+r["w"], r["y"]+r["h"]), (0, 255, 0), 2)
            cv2.putText(img, name, (r["x"], r["y"]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
        cv2.imwrite("roi_debug_full.png", img)
        print("roi_debug_full.png saved.")
else:
    print("Window not found.")
