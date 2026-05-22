import time
import os
import cv2
import numpy as np
import mss
import win32gui
import ctypes

class HealCaster:
    def __init__(self, debug=True):
        self.debug = debug
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.panel_path = os.path.join(self.base_dir, "resources", "quickslot_panel.png")
        self.heal_path = os.path.join(self.base_dir, "resources", "heal_icon.png")
        
        self.panel_template = cv2.imread(self.panel_path)
        self.heal_template = cv2.imread(self.heal_path)
        
        self._interception_initialized = False
        self._init_interception() # 객체 생성 시점에 드라이버 미리 로드 및 디바이스 캡처 수행 (첫 시전 지연 제거)
        
        if self.panel_template is None and self.debug:
            print(f"[HealCaster] ERROR: Cannot load quickslot_panel.png from {self.panel_path}")
        if self.heal_template is None and self.debug:
            print(f"[HealCaster] ERROR: Cannot load heal_icon.png from {self.heal_path}")

    def _init_interception(self):
        if not self._interception_initialized:
            try:
                import interception
                interception.auto_capture_devices()
                self._interception_initialized = True
                if self.debug:
                    print("[HealCaster] Interception driver initialized successfully.")
            except ImportError:
                if self.debug:
                    print("[HealCaster] ERROR: 'interception-python' is not installed.")

    def _find_game_hwnd(self):
        hwnd = win32gui.FindWindow(None, "Lineage Classic")
        if not hwnd:
            hwnds = []
            win32gui.EnumWindows(
                lambda h, l: l.append(h) if "Lineage" in win32gui.GetWindowText(h) else None,
                hwnds
            )
            hwnd = hwnds[0] if hwnds else None
        return hwnd

    def _get_game_center(self, hwnd):
        """게임 화면 중앙(=캐릭터 위치)의 스크린 절대 좌표"""
        client_rect = win32gui.GetClientRect(hwnd)
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        return (origin[0] + client_rect[2] // 2,
                origin[1] + client_rect[3] // 2)

    def cast_heal(self):
        """힐 스킬을 찾아서 더블클릭하고 내 캐릭터(중앙)를 클릭하는 시퀀스 실행"""
        hwnd = self._find_game_hwnd()
        if not hwnd:
            if self.debug: print("[HealCaster] ERROR: Game window 'Lineage Classic' not found.")
            return False, "게임 창을 찾을 수 없습니다."

        if not self._interception_initialized:
            return False, "Interception 드라이버 초기화 실패"

        # 2. 게임 창 활성화 및 대기
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception as e:
            if self.debug: print(f"[HealCaster] SetForegroundWindow failed: {e}")
        time.sleep(0.5) # 첫 포커스 시 입력을 완벽하게 수락하도록 대기 시간을 0.5초로 살짝 확장

        # 3. 화면 캡처
        client_rect = win32gui.GetClientRect(hwnd)
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        client_w = client_rect[2]
        client_h = client_rect[3]

        with mss.mss() as sct:
            monitor = {
                "top": origin[1],
                "left": origin[0],
                "width": client_w,
                "height": client_h
            }
            # BGR 이미지 획득
            screen = cv2.cvtColor(np.array(sct.grab(monitor)), cv2.COLOR_BGRA2BGR)
            
            # 해상도 크기 조정 비율
            scale_x = client_w / 1280.0
            scale_y = client_h / 960.0
            
            scaled_panel = self.panel_template
            scaled_heal = self.heal_template
            
            if abs(scale_x - 1.0) > 0.01 or abs(scale_y - 1.0) > 0.01:
                pw = int(self.panel_template.shape[1] * scale_x)
                ph = int(self.panel_template.shape[0] * scale_y)
                scaled_panel = cv2.resize(self.panel_template, (pw, ph), interpolation=cv2.INTER_LINEAR)
                
                hw = int(self.heal_template.shape[1] * scale_x)
                hh = int(self.heal_template.shape[0] * scale_y)
                scaled_heal = cv2.resize(self.heal_template, (hw, hh), interpolation=cv2.INTER_LINEAR)

            # 4. 퀵슬롯 패널 매칭
            res_panel = cv2.matchTemplate(screen, scaled_panel, cv2.TM_CCOEFF_NORMED)
            _, max_val_p, _, max_loc_p = cv2.minMaxLoc(res_panel)
            
            if max_val_p < 0.65:
                if self.debug: print(f"[HealCaster] Panel match failed. max_val={max_val_p:.4f}")
                return False, f"퀵슬롯 패널을 찾을 수 없습니다. (신뢰도: {max_val_p:.2f})"
            
            px, py = max_loc_p
            pw, ph = scaled_panel.shape[1], scaled_panel.shape[0]
            
            # 5. 퀵슬롯 패널 영역 자르기
            panel_crop = screen[py:py+ph, px:px+pw]
            
            # 6. 잘라낸 패널 내에서 힐 스킬 아이콘 매칭
            res_heal = cv2.matchTemplate(panel_crop, scaled_heal, cv2.TM_CCOEFF_NORMED)
            _, max_val_h, _, max_loc_h = cv2.minMaxLoc(res_heal)
            
            if max_val_h < 0.65:
                if self.debug: print(f"[HealCaster] Heal icon match failed. max_val={max_val_h:.4f}")
                return False, f"힐 아이콘을 퀵슬롯에서 찾을 수 없습니다. (신뢰도: {max_val_h:.2f})"
            
            hx, hy = max_loc_h
            hw_w, hw_h = scaled_heal.shape[1], scaled_heal.shape[0]
            
            # 힐 아이콘의 전체 화면 기준 절대 좌표 계산
            heal_center_x = origin[0] + px + hx + hw_w // 2
            heal_center_y = origin[1] + py + hy + hw_h // 2
            
            if self.debug:
                print(f"[HealCaster] Found Panel at ({px}, {py}) score={max_val_p:.4f}")
                print(f"[HealCaster] Found Heal at relative ({hx}, {hy}) score={max_val_h:.4f}")
                print(f"[HealCaster] Click Target Screen coords: ({heal_center_x}, {heal_center_y})")

            import interception
            
            # 7. 클릭 직전 게임 창 포커스 재획득 (대시보드 Tkinter가 포커스를 뺏는 현상 방지)
            try:
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
            time.sleep(0.3)
            
            # 힐 스킬 더블클릭 수행 (완전 드라이버 통합 방식)
            interception.move_to(heal_center_x, heal_center_y)
            time.sleep(0.25)
            
            interception.click()
            time.sleep(0.15)
            interception.click()
            
            time.sleep(0.4)  # 힐 스킬 활성화 및 캐스팅 타겟 대기
            
            # 8. 화면 중앙 (내 캐릭터) 클릭 (하단 정보 패널을 제외한 실 게임화면의 중앙)
            center_x = origin[0] + client_w // 2
            center_y = origin[1] + py // 2
            
            interception.move_to(center_x, center_y)
            time.sleep(0.25)
            
            interception.click()
            
            if self.debug:
                print(f"[HealCaster] Clicked Character Center: ({center_x}, {center_y})")
                print("[HealCaster] Heal execution complete!")
                
            return True, "힐 시전 완료!"
