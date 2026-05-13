import cv2
import numpy as np
import mss
import json
import time
import win32gui
import pydirectinput

class CharacterEngine:
    def __init__(self, mapping_path='resources/monster_mapping.json'):
        self.mapping = json.load(open(mapping_path, 'r', encoding='utf-8'))
        self.templates = {}
        self.prev_frame = None  # For motion detection
        
        # Load templates with multi-scaling (80%, 100%, 120%)
        count = 0
        for name, path in self.mapping.items():
            img = cv2.imread(path)
            if img is not None:
                self.templates[name] = img
                count += 1
            if count > 20: break 
            
        self.sct = mss.mss()
        self.hwnd = self.find_lineage_window()
        
    def find_lineage_window(self):
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "Lineage Classic" in title:
                    windows.append(hwnd)
        windows = []
        win32gui.EnumWindows(callback, windows)
        return windows[0] if windows else None

    def capture_screen(self):
        if not self.hwnd: return None
        rect = win32gui.GetWindowRect(self.hwnd)
        monitor = {"top": rect[1], "left": rect[0], "width": rect[2]-rect[0], "height": rect[3]-rect[1]}
        img = np.array(self.sct.grab(monitor))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR), rect

    def detect_characters(self, screen):
        results = []
        
        # 1. Motion Detection (Frame Differencing)
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if self.prev_frame is not None:
            frame_delta = cv2.absdiff(self.prev_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                if cv2.contourArea(cnt) < 500: # Ignore tiny noise
                    continue
                (x, y, w, h) = cv2.boundingRect(cnt)
                # Filter by character size approx
                if 20 < w < 200 and 20 < h < 200:
                    results.append({
                        "name": "Moving Entity",
                        "pos": (x, y),
                        "size": (w, h),
                        "conf": 0.8
                    })
        
        self.prev_frame = gray
        
        # 2. Background Masking (Finding objects that aren't ground)
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        # Background: Brown (dirt) or Green (grass)
        # We find what is NOT these colors
        lower_dirt = np.array([10, 20, 20])
        upper_dirt = np.array([30, 255, 200])
        mask_dirt = cv2.inRange(hsv, lower_dirt, upper_dirt)
        
        lower_grass = np.array([35, 20, 20])
        upper_grass = np.array([85, 255, 200])
        mask_grass = cv2.inRange(hsv, lower_grass, upper_grass)
        
        mask_bg = cv2.bitwise_or(mask_dirt, mask_grass)
        mask_inv = cv2.bitwise_not(mask_bg) # This mask contains non-ground objects
        
        # Clean up noise
        kernel = np.ones((5,5), np.uint8)
        mask_inv = cv2.morphologyEx(mask_inv, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(mask_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 300 < area < 5000: # Typical character size area
                x, y, w, h = cv2.boundingRect(cnt)
                results.append({
                    "name": "Static Entity",
                    "pos": (x, y),
                    "size": (w, h),
                    "conf": 0.7
                })

        # 3. Multi-Scale Template Matching
        for name, template in self.templates.items():
            for scale in [0.8, 1.0, 1.2]:
                resized = cv2.resize(template, None, fx=scale, fy=scale)
                res = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
                threshold = 0.6 
                loc = np.where(res >= threshold)
                
                h, w = resized.shape[:2]
                found = False
                for pt in zip(*loc[::-1]):
                    results.append({
                        "name": name,
                        "pos": (pt[0], pt[1]),
                        "size": (w, h),
                        "conf": res[pt[1], pt[0]]
                    })
                    found = True
                    break
                if found: break # found at one scale, move to next template
        return results

    def move_to_target(self, target, window_rect):
        # Calculate screen coordinates
        # target["pos"] is relative to window
        screen_x = window_rect[0] + target["pos"][0] + target["size"][0] // 2
        screen_y = window_rect[1] + target["pos"][1] + target["size"][1] // 2
        
        print(f"Moving to {target['name']} at ({screen_x}, {screen_y})")
        # Use pydirectinput for stealth/bypass
        pydirectinput.moveTo(screen_x, screen_y, duration=0.2)

if __name__ == "__main__":
    engine = CharacterEngine()
    print("Character Engine started. Press Ctrl+C to stop.")
    try:
        while True:
            screen_data = engine.capture_screen()
            if screen_data is None:
                print("Lineage window not found.")
                time.sleep(1)
                continue
            
            screen, rect = screen_data
            targets = engine.detect_characters(screen)
            
            if targets:
                # Pick the best target (highest confidence)
                best = max(targets, key=lambda x: x["conf"])
                print(f"Detected: {best['name']} ({best['conf']:.2f})")
                engine.move_to_target(best, rect)
                
            time.sleep(0.5) # Scanning interval
    except KeyboardInterrupt:
        print("Engine stopped.")
