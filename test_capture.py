import os
import time
import win32gui
import win32con
import mss
import mss.tools
import numpy as np
import cv2

def find_lineage_window():
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "Lineage Classic" in title:
                windows.append((hwnd, title))
    
    windows = []
    win32gui.EnumWindows(callback, windows)
    return windows

def capture_window(hwnd, output_path):
    # Get window coordinates
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    
    print(f"Window found: {win32gui.GetWindowText(hwnd)}")
    print(f"Coordinates: L={left}, T={top}, R={right}, B={bottom} (Size: {width}x{height})")
    
    with mss.mss() as sct:
        # The screen part to capture
        monitor = {"top": top, "left": left, "width": width, "height": height}
        
        # Grab the data
        sct_img = sct.grab(monitor)
        
        # Convert to raw bytes
        img = np.array(sct_img)
        
        # Check if the image is black (all zeros)
        # sct_img is BGRA by default
        if np.all(img[:, :, :3] == 0):
            print("WARNING: Captured image is ALL BLACK. This might be due to anti-cheat protection.")
        else:
            print("Capture Success: Image contains data.")
            
        # Save to file
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=output_path)
        print(f"Screenshot saved to: {output_path}")

if __name__ == "__main__":
    # Ensure docs directory exists
    docs_dir = os.path.join(os.getcwd(), "docs")
    if not os.path.exists(docs_dir):
        os.makedirs(docs_dir)
        
    output_file = os.path.join(docs_dir, "03_test_capture.png")
    
    lineage_windows = find_lineage_window()
    if not lineage_windows:
        print("Error: Lineage Classic window not found.")
    else:
        hwnd, title = lineage_windows[0]
        capture_window(hwnd, output_file)
