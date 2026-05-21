import cv2
import numpy as np
import os
import json
import pytesseract
import re

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class PixelOCR:
    def __init__(self, db_path="resources/pixel_glyph_db.json", fallback_ocr_fn=None):
        if db_path == "resources/pixel_glyph_db.json":
            db_path = os.path.join(os.path.dirname(__file__), "resources", "pixel_glyph_db.json")
        self.db_path = db_path
        self.db = {}
        self.load_db()
        self.fallback_ocr_fn = fallback_ocr_fn

    def load_db(self):
        # Default built-in signatures harvested from gameplay screens
        # Keys must be string representations of tuples for JSON compatibility
        self.db = {
            # --- HP/MP Anchored Glyphs ---
            # H
            str((33, 99, 231, 231, 231, 255, 255, 231, 231, 231, 198, 132)): "H",
            # P
            str((62, 126, 231, 231, 231, 231, 247, 254, 240, 224, 192, 128)): "P",
            # :
            str((3, 3, 3, 0, 0, 0, 1, 3, 3, 1)): ":",
            # /
            str((3, 3, 3, 4, 12, 12, 12, 12, 16, 16, 16, 16)): "/",
            str((3, 3, 3, 4, 12, 12, 12, 12, 16, 16, 16)): "/",
            str((6, 15, 31, 31, 15, 15, 15)): "/", 
            # 9
            str((30, 30, 39, 231, 231, 127, 63, 7, 134, 198, 248, 248)): "9",
            str((30, 30, 39, 231, 231, 127, 63, 7, 134, 198)): "9",
            # 7
            str((63, 63, 193, 6, 6, 30, 30, 30, 30, 30, 24, 8)): "7",
            str((63, 63, 193, 6, 6, 30, 30, 30, 30, 30)): "7",
            str((126, 255, 391, 398, 12, 60, 60)): "7", 
            # 5
            str((255, 255, 224, 252, 254, 7, 7, 39, 199, 199, 62, 60)): "5",
            # 3
            str((60, 62, 199, 135, 7, 62, 62, 7, 7, 199, 62, 62)): "3",
            str((60, 62, 199, 135, 7, 62, 62, 7, 7, 199)): "3",
            # 2
            str((60, 62, 199, 135, 7, 14, 30, 32, 96, 225, 255, 255)): "2",
            str((60, 62, 199, 135, 7, 14, 30, 32, 96, 224)): "2",
            str((124, 252, 399, 399, 15, 62, 60)): "2", 
            str((60, 62, 199, 135, 7, 30, 30)): "2",
            # 1
            str((1, 1, 1)): "1",
            str((6, 15, 31, 15, 15, 15, 15)): "1",
            # 4
            str((4, 6, 31, 31, 39, 231, 231)): "4",
            # 6
            str((60, 62, 231, 231, 224, 252, 254)): "6",
            # %
            str((33, 33, 249, 251, 38, 24, 24)): "%",
            str((33, 97, 249, 116, 36, 24, 24, 38)): "%",
            # -
            str((15, 15)): "-",
            str((255, 255)): "-",

            # --- Perfected Character Stats Panel Glyphs (Loaded from Master JSON) ---
        }
        
        # Load user-saved dictionary to overwrite or extend
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    user_db = json.load(f)
                    self.db.update(user_db)
            except Exception as e:
                print(f"[PixelOCR] Error loading user database: {e}")

    def save_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.db, f, indent=4)
        except Exception as e:
            print(f"[PixelOCR] Error saving database: {e}")

    def register_signature(self, signature, char):
        sig_str = str(signature)
        if sig_str not in self.db:
            self.db[sig_str] = char
            self.save_db()
            print(f"[PixelOCR] REGISTERED NEW GLYPH: Char '{char}' -> Sig {sig_str}")

    def read_text(self, crop_img, threshold_val=120, is_hpmp=False, name="unknown", raw_img=None):
        # Define regex patterns for high-precision type validation
        patterns = {
            "HP_Bar": r"^\d+/\d+$",
            "MP_Bar": r"^\d+/\d+$",
            "LEVEL": r"^\d+$",
            "EXP": r"^\d+(\.\d+)?%?$",
            "AC": r"^-?\d*$",
            "MR": r"^\d+%?$",
            "WEIGHT": r"^\d+%?$",
            "FOOD": r"^\d+%?$",
            "LAWFUL": r"^-?\d+$"
        }
        
        pattern = patterns.get(name)
        if not pattern:
            return self._read_text_single(crop_img, threshold_val, is_hpmp, name)
            
        # Sweeping thresholds to dynamically bypass dynamic background shifts!
        thresholds = [120, 110, 130, 115, 125, 100, 140]
        best_text = ""
        best_q_count = 999
        
        for th in thresholds:
            text = self._read_text_single(crop_img, th, is_hpmp, name)
            
            if name in ["HP_Bar", "MP_Bar"]:
                text = re.sub(r"[^\d/]", "", text)
            
            # Format correction helper inside loop for compliance checks
            if name in ["EXP", "MR", "WEIGHT", "FOOD"]:
                if len(text) > 0 and text[-1] not in ['%', 'g']:
                    text = text + '%'
                text = text.replace("g", "%")
                
            # If the text matches the regular expression and has no unknown characters, return immediately!
            if re.match(pattern, text) and '?' not in text:
                return text
                
            q_count = text.count('?')
            if q_count < best_q_count:
                best_q_count = q_count
                best_text = text
                
        # If lookup failed to produce a valid pattern match or has unknown characters, invoke AI fallback!
        if (best_q_count > 0 or not re.match(pattern, best_text)) and self.fallback_ocr_fn:
            # Use raw_img if provided (ensures high-precision AI fallback on clean colors!)
            target_img = raw_img if raw_img is not None else crop_img
            ai_text = self.fallback_ocr_fn(target_img, name)
            if ai_text and re.match(pattern, ai_text) and '?' not in ai_text:
                print(f"[PixelOCR] AI Fallback resolved '{name}' (pattern mismatch or '?'): '{best_text}' -> '{ai_text}'")
                # Auto-seed the unknown glyphs using the AI recognized text
                self._seed_unknown_glyphs(crop_img, threshold_val, is_hpmp, name, ai_text)
                return ai_text
                
        return best_text

    def _seed_unknown_glyphs(self, crop_img, threshold_val, is_hpmp, name, target_text):
        try:
            gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, threshold_val, 1, cv2.THRESH_BINARY)
            
            if not is_hpmp and thresh.shape[0] > 10:
                thresh = thresh[:-2, :]
                
            num_labels, labels_im, stats, centroids = cv2.connectedComponentsWithStats(thresh)
            for i in range(1, num_labels):
                if stats[i, cv2.CC_STAT_AREA] < 2:
                    thresh[labels_im == i] = 0
                    
            col_sums = np.sum(thresh, axis=0)
            in_char = False
            segments = []
            start = 0
            for x in range(thresh.shape[1]):
                active = col_sums[x] > 0
                if active and not in_char:
                    in_char = True
                    start = x
                elif not active and in_char:
                    in_char = False
                    segments.append((start, x))
            if in_char:
                segments.append((start, thresh.shape[1]))
                
            cleaned_target = target_text
            
            if len(segments) == len(cleaned_target):
                for idx, (x1, x2) in enumerate(segments):
                    glyph = thresh[:, x1:x2]
                    row_sums = np.sum(glyph, axis=1)
                    active_rows = np.where(row_sums > 0)[0]
                    if len(active_rows) > 0:
                        y1, y2 = active_rows[0], active_rows[-1] + 1
                        glyph = glyph[y1:y2, :]
                    else:
                        continue
                        
                    row_vals = []
                    for r in range(glyph.shape[0]):
                        val = 0
                        for c in range(glyph.shape[1]):
                            if glyph[r, c] == 1:
                                val |= (1 << (glyph.shape[1] - 1 - c))
                        row_vals.append(val)
                        
                    sig_str = str(tuple(row_vals))
                    char = cleaned_target[idx]
                    
                    if sig_str not in self.db:
                        self.register_signature(tuple(row_vals), char)
            else:
                print(f"[PixelOCR] Segment mismatch for '{name}' during seeding: Segments={len(segments)} TargetLen={len(cleaned_target)}")
        except Exception as e:
            print(f"[PixelOCR] Error seeding glyphs for '{name}': {e}")

    def _read_text_single(self, crop_img, threshold_val=130, is_hpmp=False, name="unknown"):
        # 1. Grayscale
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
        
        # 2. Stable Binarization
        _, thresh = cv2.threshold(gray, threshold_val, 1, cv2.THRESH_BINARY)
        
        # 3. For stats panel, chop off bottom 2 rows to bypass horizontal line if crop is tall!
        if not is_hpmp and thresh.shape[0] > 10:
            thresh = thresh[:-2, :]
            
        # 4. Remove small isolated single-pixel noise
        num_labels, labels_im, stats, centroids = cv2.connectedComponentsWithStats(thresh)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] < 2:
                thresh[labels_im == i] = 0
                
        # 5. Segment into columns
        col_sums = np.sum(thresh, axis=0)
        in_char = False
        segments = []
        start = 0
        for x in range(thresh.shape[1]):
            active = col_sums[x] > 0
            if active and not in_char:
                in_char = True
                start = x
            elif not active and in_char:
                in_char = False
                segments.append((start, x))
        if in_char:
            segments.append((start, thresh.shape[1]))
            
        # 6. Extract and recognize each character
        result_chars = []
        
        for idx, (x1, x2) in enumerate(segments):
            glyph = thresh[:, x1:x2]
            row_sums = np.sum(glyph, axis=1)
            active_rows = np.where(row_sums > 0)[0]
            if len(active_rows) > 0:
                y1, y2 = active_rows[0], active_rows[-1] + 1
                glyph = glyph[y1:y2, :]
            else:
                continue
                
            # Compute Signature
            row_vals = []
            for r in range(glyph.shape[0]):
                val = 0
                for c in range(glyph.shape[1]):
                    if glyph[r, c] == 1:
                        val |= (1 << (glyph.shape[1] - 1 - c))
                row_vals.append(val)
                
            signature = tuple(row_vals)
            sig_str = str(signature)
            
            # Lookup
            if sig_str in self.db:
                result_chars.append(self.db[sig_str])
            else:
                # Print glyph in console for debugging/logging
                print(f"[PixelOCR] Unknown glyph in '{name}' Segment {idx}: Width={glyph.shape[1]} Sig={signature}")
                for r in range(glyph.shape[0]):
                    row_str = "".join(["#" if glyph[r, c] == 1 else "." for c in range(glyph.shape[1])])
                    print(f"  # {row_str}")
                result_chars.append("?")
                    
        return "".join(result_chars)
