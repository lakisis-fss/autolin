import os
import cv2
import numpy as np
import mss
import win32gui

def get_lineage_rect():
    def callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "Lineage Classic" in title:
                windows.append(win32gui.GetWindowRect(hwnd))
    windows = []
    win32gui.EnumWindows(callback, windows)
    return windows[0] if windows else None

def check_hp(debug=False):
    rect = get_lineage_rect()
    if not rect:
        print("Error: Lineage Classic window not found.")
        return None
        
    left, top, right, bottom = rect
    
    # HP Bar ROI (Relative to window)
    # Based on research: x=286, y=781, w=280, h=31
    roi_x, roi_y, roi_w, roi_h = 286, 781, 280, 31
    
    with mss.mss() as sct:
        monitor = {
            "top": top + roi_y,
            "left": left + roi_x,
            "width": roi_w,
            "height": roi_h
        }
        
        sct_img = sct.grab(monitor)
        img = np.array(sct_img)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR) # Convert BGRA to BGR
        hsv = cv2.cvtColor(hsv, cv2.COLOR_BGR2HSV)
        
        # Color ranges for 'Red' in Lineage Classic HP bar
        # Usually high saturation and value in the red hue
        lower_red1 = np.array([0, 150, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 150, 100])
        upper_red2 = np.array([180, 255, 255])
        
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)
        
        # Calculate HP Percent
        # Use column-wise projection to find the horizontal width of the red bar
        col_sums = np.sum(mask, axis=0) # Sum vertically
        red_cols = np.where(col_sums > (roi_h * 0.1 * 255))[0] # At least 10% of the column height is red
        
        if len(red_cols) == 0:
            hp_percent = 0
        else:
            # The filled width is the rightmost red column
            filled_width = np.max(red_cols) + 1
            hp_percent = (filled_width / roi_w) * 100
            
        if debug:
            # Full debug: Create a copy of the ROI and draw the detected width
            debug_img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            cv2.line(debug_img, (0, roi_h // 2), (int(filled_width), roi_h // 2), (0, 255, 0), 2)
            cv2.putText(debug_img, f"{hp_percent:.1f}%", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.imwrite(os.path.join("docs", "06_hp_mask_debug.png"), mask)
            cv2.imwrite(os.path.join("docs", "07_hp_detect_crop.png"), debug_img)
            print(f"Debug images saved to docs/06_hp_mask_debug.png and docs/07_hp_detect_crop.png")
            
        return hp_percent

if __name__ == "__main__":
    hp = check_hp(debug=True)
    if hp is not None:
        print(f"Current HP: {hp:.1f}%")
