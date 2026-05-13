import cv2
import numpy as np
import mss
import json
import time
import os
import win32gui
import win32con
import pydirectinput
import tkinter as tk
from threading import Thread
import logging
import queue
import ctypes

# Enable DPI Awareness for high-precision coordinates
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

# Setup Logging
logging.basicConfig(filename='engine.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("Engine Script Started (Advanced Filtering)")

class OverlayWindow:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.config(bg="black")
        self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
        self.labels = {}

    def update_label(self, target_id, text, x, y, color="lime"):
        if target_id not in self.labels:
            lbl = tk.Label(self.root, text=text, fg=color, bg="black", font=("Arial", 12, "bold"))
            lbl.place(x=x, y=y)
            self.labels[target_id] = lbl
        else:
            self.labels[target_id].config(text=text, fg=color)
            self.labels[target_id].place(x=x, y=y)
            
    def clear_labels(self):
        for lbl in self.labels.values():
            lbl.destroy()
        self.labels = {}

class CharEngine:
    def __init__(self, root, monsters_path='resources/monster_mapping.json', items_path='resources/item_mapping.json'):
        self.root = root
        self.monsters = json.load(open(monsters_path, 'r', encoding='utf-8'))
        self.items = json.load(open(items_path, 'r', encoding='utf-8'))
        
        self.templates = {"monster": {}, "item": {}}
        self.monster_names = []
        # Load ALL Monsters/Animals from synced mapping
        print(f"Loading {len(self.monsters)} monster/animal templates...")
        for name, path in self.monsters.items():
            img = cv2.imread(path)
            if img is not None: 
                self.templates["monster"][name] = img
                self.monster_names.append(name)
        
        self.scan_index = 0 # For rotating scan optimization
        self.priority_targets = ["사슴", "멧돼지", "토끼", "개구리", "오크", "고블린"] # Always check these
            
        # Load Items
        for name, path in self.items.items():
            img = cv2.imread(path)
            if img is not None: self.templates["item"][name] = img

        self.prev_frame = None
        self.q = queue.Queue()
        self.overlay = OverlayWindow(self.root)
        
        self.worker = Thread(target=self.detection_loop, daemon=True)
        self.worker.start()
        self.update_ui()

    def find_window(self, title_part="Lineage Classic"):
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if title_part.lower() in title:
                    windows.append(hwnd)
        windows = []
        win32gui.EnumWindows(callback, windows)
        return windows[0] if windows else None

    def is_player(self, frame, x, y, w, h):
        roi_y_start = max(0, y - 25)
        roi_y_end = y + 5
        roi_x_start = x
        roi_x_end = x + w
        
        name_roi = frame[roi_y_start:roi_y_end, roi_x_start:roi_x_end]
        if name_roi.size == 0: return False
        
        hsv = cv2.cvtColor(name_roi, cv2.COLOR_BGR2HSV)
        
        # Blue/Cyan range (Lawful names)
        mask_blue = cv2.inRange(hsv, np.array([90, 50, 50]), np.array([130, 255, 255]))
        # Red range (PK names)
        mask_red = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255]))
        
        b_count = cv2.countNonZero(mask_blue)
        r_count = cv2.countNonZero(mask_red)
        
        # Increased threshold significantly to ensure we don't ignore monsters with red/blue tints
        if b_count > 100 or r_count > 100: 
            return True
        return False

    def detection_loop(self):
        with mss.mss() as sct:
            while True:
                try:
                    hwnd = self.find_window()
                    if not hwnd:
                        time.sleep(1)
                        continue
                    
                    # Get Client Area (excluding borders and title bar)
                    rect = win32gui.GetClientRect(hwnd)
                    point = win32gui.ClientToScreen(hwnd, (0, 0))
                    
                    # width, height of client area
                    w, h = rect[2], rect[3]
                    if w <= 0 or h <= 0:
                        time.sleep(1)
                        continue
                        
                    monitor = {"top": point[1], "left": point[0], "width": w, "height": h}
                    
                    sct_img = sct.grab(monitor)
                    if not sct_img:
                        continue
                        
                    frame = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)
                    if frame is None or frame.size == 0:
                        continue
                    
                    found_targets = []

                    # 1. Item Recognition (Priority)
                    for name, template in self.templates["item"].items():
                        res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
                        max_val = np.max(res)
                        if max_val > 0.75: # Standard threshold
                            _, _, _, max_loc = cv2.minMaxLoc(res)
                            # Screen coordinates: (max_loc[0] + client_left, max_loc[1] + client_top)
                            found_targets.append({"type": "item", "name": name, "x": max_loc[0] + point[0], "y": max_loc[1] + point[1], "w": template.shape[1], "h": template.shape[0], "conf": max_val + 1.0}) # Increased priority

                    # 2. Monster/Animal Recognition (Optimized Static Scan)
                    # We rotate through templates to keep FPS high while maintaining wide coverage
                    batch_size = 20
                    search_list = self.priority_targets.copy()
                    
                    if self.monster_names:
                        current_batch = self.monster_names[self.scan_index:self.scan_index + batch_size]
                        self.scan_index = (self.scan_index + batch_size) % len(self.monster_names)
                        search_list = list(set(self.priority_targets + current_batch))
                    
                    scales = [1.0, 0.9, 1.1] # Base size first
                    for scale in scales:
                        if scale != 1.0:
                            s_frame = cv2.resize(frame, None, fx=scale, fy=scale)
                        else:
                            s_frame = frame
                            
                        for name in search_list:
                            if name not in self.templates["monster"]: continue
                            template = self.templates["monster"][name]
                            
                            # Skip if template is larger than (scaled) frame
                            if template.shape[0] > s_frame.shape[0] or template.shape[1] > s_frame.shape[1]:
                                continue
                                
                            res = cv2.matchTemplate(s_frame, template, cv2.TM_CCOEFF_NORMED)
                            max_val = np.max(res)
                            
                            # Recognition Threshold
                            if max_val > 0.7: 
                                _, _, _, max_loc = cv2.minMaxLoc(res)
                                tx = int(max_loc[0] / scale) + point[0]
                                ty = int(max_loc[1] / scale) + point[1]
                                tw = int(template.shape[1] / scale)
                                th = int(template.shape[0] / scale)
                                
                                if not self.is_player(frame, int(max_loc[0]/scale), int(max_loc[1]/scale), tw, th):
                                    found_targets.append({"type": "monster", "name": name, "x": tx, "y": ty, "w": tw, "h": th, "conf": max_val + 0.5}) # High priority
                                    
                        # Performance optimization: if found at 1.0, stop scaling
                        if found_targets and scale == 1.0: break

                    # Match Items (Always check items as they are few)
                    for name, template in self.templates["item"].items():
                        res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
                        max_val = np.max(res)
                        if max_val > 0.75:
                            _, _, _, max_loc = cv2.minMaxLoc(res)
                            found_targets.append({"type": "item", "name": name, "x": max_loc[0] + point[0], "y": max_loc[1] + point[1], "w": template.shape[1], "h": template.shape[0], "conf": max_val + 0.5})

                    # 3. Motion Detection (Fallback ONLY)
                    # Skip if we already found a high-confidence static target
                    if not any(t["type"] in ["monster", "item"] for t in found_targets):
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        gray = cv2.GaussianBlur(gray, (21, 21), 0)
                        if self.prev_frame is not None and self.prev_frame.shape == gray.shape:
                            delta = cv2.absdiff(self.prev_frame, gray)
                            thresh = cv2.threshold(delta, 50, 255, cv2.THRESH_BINARY)[1]
                            thresh = cv2.dilate(thresh, None, iterations=2)
                            
                            # Global Motion Filter: If too many pixels are moving, it's a camera scroll
                            motion_density = cv2.countNonZero(thresh) / (w * h)
                            if motion_density < 0.04: # Threshold for camera scroll (approx 4% of 1280x960)
                                cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                                for c in cnts:
                                    area = cv2.contourArea(c)
                                    if 800 < area < 10000: # Typical monster size range
                                        x, y, mw, mh = cv2.boundingRect(c)
                                        # Strict Aspect Ratio and Center (Player) Exclusion
                                        aspect_ratio = mh / float(mw) if mw > 0 else 0
                                        is_center = (w//2 - 120 < x < w//2 + 120) and (h//2 - 120 < y < h//2 + 120)
                                        
                                        if 0.5 < aspect_ratio < 3.0 and not is_center:
                                            if y < h * 0.8: # Ignore UI area at bottom
                                                if not self.is_player(frame, x, y, mw, mh):
                                                    found_targets.append({"type": "motion", "name": "Moving Enemy", "x": x + point[0], "y": y + point[1], "w": mw, "h": mh, "conf": 0.2})
                        self.prev_frame = gray
                    
                    if found_targets:
                        best = max(found_targets, key=lambda x: x["conf"])
                        self.q.put(best)
                        logging.info(f"Precise Tracking: {best['name']} at {best['x']}, {best['y']}")
                    else:
                        self.q.put(None)

                    time.sleep(0.3)

                except Exception as e:
                    logging.error(f"Worker Loop Error: {e}")
                    time.sleep(1)

    def update_ui(self):
        try:
            # Force overlay to stay on top periodically
            self.root.lift()
            self.root.attributes("-topmost", True)
            
            while not self.q.empty():
                target = self.q.get_nowait()
                if target:
                    color = "gold" if target["type"] == "item" else "lime"
                    tx = target["x"] + target["w"] // 2
                    ty = target["y"] - 20
                    self.overlay.update_label("best", f"Detected {target['type'].upper()}: {target['name']}", tx, ty, color=color)
                    pydirectinput.moveTo(tx, ty + 20)
                else:
                    self.overlay.clear_labels()
        except Exception:
            pass
        self.root.after(100, self.update_ui)

if __name__ == "__main__":
    root = tk.Tk()
    engine = CharEngine(root)
    logging.info("Advanced Entity Filter HUD Running")
    root.mainloop()
