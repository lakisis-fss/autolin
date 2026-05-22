import cv2
import numpy as np
import mss
import win32gui
from paddleocr import PaddleOCR
import re
import os

class ExpFilterTester:
    def __init__(self):
        self.base_resolution = (1280, 960)
        self.char_panel_roi = {"x": 4, "y": 710, "w": 226, "h": 249}
        
        # Use absolute path to load the anchor
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        anchor_path = os.path.join(base_dir, "resources", "new_anchor_tabs.png")
        self.char_anchor = cv2.imread(anchor_path)
        if self.char_anchor is None:
            print(f"Warning: Could not load anchor from {anchor_path}")
            
        self.ocr_engine = PaddleOCR(
            use_doc_unwarping=False,
            use_doc_orientation_classify=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
            lang='en'
        )
        self.rec_model = self.ocr_engine.paddlex_pipeline._pipeline.text_rec_model

    def get_lineage_rect(self):
        hwnd = win32gui.FindWindow(None, "Lineage Classic")
        if not hwnd:
            hwnds = []
            win32gui.EnumWindows(lambda h, l: l.append(h) if "Lineage" in win32gui.GetWindowText(h) else None, hwnds)
            if hwnds: hwnd = hwnds[0]
            else: return None
        rect = win32gui.GetWindowRect(hwnd)
        client_rect = win32gui.GetClientRect(hwnd)
        client_origin = win32gui.ClientToScreen(hwnd, (0, 0))
        return {"hwnd": hwnd, "rect": rect, "client_rect": client_rect, "client_origin": client_origin}

    def capture_custom_roi(self, info, roi, sct):
        scale_x = info["client_rect"][2] / self.base_resolution[0]
        scale_y = info["client_rect"][3] / self.base_resolution[1]
        monitor = {
            "top": info["client_origin"][1] + int(roi["y"] * scale_y),
            "left": info["client_origin"][0] + int(roi["x"] * scale_x),
            "width": int(roi["w"] * scale_x),
            "height": int(roi["h"] * scale_y)
        }
        return cv2.cvtColor(np.array(sct.grab(monitor)), cv2.COLOR_BGRA2BGR)

    def run_test(self):
        info = self.get_lineage_rect()
        if not info:
            print("Lineage window not found!")
            return
            
        with mss.mss() as sct:
            client_w = info["client_rect"][2]
            client_h = info["client_rect"][3]
            monitor = {
                "top": info["client_origin"][1],
                "left": info["client_origin"][0],
                "width": client_w,
                "height": client_h
            }
            full_screen = cv2.cvtColor(np.array(sct.grab(monitor)), cv2.COLOR_BGRA2BGR)
            
            scale_x = client_w / self.base_resolution[0]
            scale_y = client_h / self.base_resolution[1]
            
            char_panel = None
            if self.char_anchor is not None:
                scaled_char_anchor = self.char_anchor
                if abs(scale_x - 1.0) > 0.01 or abs(scale_y - 1.0) > 0.01:
                    w_ca = int(self.char_anchor.shape[1] * scale_x)
                    h_ca = int(self.char_anchor.shape[0] * scale_y)
                    scaled_char_anchor = cv2.resize(self.char_anchor, (w_ca, h_ca), interpolation=cv2.INTER_LINEAR)
                
                res_char = cv2.matchTemplate(full_screen, scaled_char_anchor, cv2.TM_CCOEFF_NORMED)
                _, max_val_c, _, max_loc_c = cv2.minMaxLoc(res_char)
                
                if max_val_c > 0.65:
                    x_c, y_c = max_loc_c
                    panel_x = max(0, x_c - int(125 * scale_x))
                    panel_y = y_c
                    w_c = int(226 * scale_x)
                    h_c = int(249 * scale_y)
                    
                    char_panel = full_screen[panel_y:panel_y+h_c, panel_x:panel_x+w_c]
            
            if char_panel is None:
                print("Falling back to static character panel capture...")
                char_panel = self.capture_custom_roi(info, self.char_panel_roi, sct)
                
            if char_panel is None:
                print("Failed to capture character panel completely.")
                return
                
            if char_panel.shape[1] != 226 or char_panel.shape[0] != 249:
                char_panel = cv2.resize(char_panel, (226, 249), interpolation=cv2.INTER_LINEAR)
                
            # EXP ROI
            roi = {"x": 120, "y": 60, "w": 75, "h": 13}
            crop = char_panel[roi["y"]:roi["y"]+roi["h"], roi["x"]:roi["x"]+roi["w"]]
            
            # --- 1. Original (Raw BGR) + 4x upscale ---
            resized_orig = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            res_orig = list(self.rec_model(resized_orig))
            text_orig = res_orig[0].get("rec_text", "").strip() if res_orig else "Failed"
            
            # --- 2. Thresholding only (Standard Grayscale -> Binary) ---
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
            resized_thresh = cv2.resize(thresh, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
            resized_thresh_3ch = cv2.cvtColor(resized_thresh, cv2.COLOR_GRAY2BGR)
            res_thresh = list(self.rec_model(resized_thresh_3ch))
            text_thresh = res_thresh[0].get("rec_text", "").strip() if res_thresh else "Failed"
            
            # --- 3. White Color Filter (Erases orange and gray background) ---
            b, g, r = cv2.split(crop)
            
            for threshold_val in [140, 150, 160, 170, 180]:
                mask = (r > threshold_val) & (g > threshold_val) & (b > threshold_val)
                filtered = np.zeros_like(crop)
                filtered[mask] = [255, 255, 255]
                
                resized_filtered = cv2.resize(filtered, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
                res_filtered = list(self.rec_model(resized_filtered))
                text_filtered = res_filtered[0].get("rec_text", "").strip() if res_filtered else "Failed"
                print(f"[White Filter > {threshold_val}] Raw text resolved: {text_filtered}")
                
            print(f"[Original Raw BGR] Raw text resolved: {text_orig}")
            print(f"[Standard Threshold 120] Raw text resolved: {text_thresh}")

if __name__ == "__main__":
    tester = ExpFilterTester()
    tester.run_test()

if __name__ == "__main__":
    tester = ExpFilterTester()
    tester.run_test()
