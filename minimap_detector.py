import os
import cv2
import numpy as np
from PIL import ImageGrab
import win32gui
import math

class MinimapDetector:
    """리니지 클래식 미니맵 비전 분석 기반 장애물 및 통행 가능 구역 실시간 탐지기"""
    
    def __init__(self, debug=True):
        self.debug = debug
        self.base_resolution = (1280, 960)
        
        # 1280x960 해상도 기준 미니맵 ROI [top, left, width, height]
        # 좌상단 UI 패널에 고정되어 있음
        self.minimap_roi = {"x": 15, "y": 15, "w": 160, "h": 160}
        
        # HSV 필터용 범위 (밝은 녹색/연두색 = 통행 가능 영역)
        # 게임 환경에 따라 조정 가능하도록 파라미터화
        self.lower_green = np.array([35, 40, 40])
        self.upper_green = np.array([85, 255, 255])
        
        # 미니맵 픽셀 대 월드 타일 축척 (1.5 픽셀 = 1 타일)
        self.pixel_to_tile_ratio = 1.5
        
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

    def _get_game_rect(self):
        hwnd = self._find_game_hwnd()
        if not hwnd:
            return None
        rect = win32gui.GetWindowRect(hwnd)
        client_rect = win32gui.GetClientRect(hwnd)
        client_origin = win32gui.ClientToScreen(hwnd, (0, 0))
        return {
            "hwnd": hwnd,
            "rect": rect,
            "client_rect": client_rect,
            "client_origin": client_origin
        }

    def capture_minimap(self, game_info=None):
        """게임 화면에서 미니맵 영역을 크롭하여 (160, 160) 크기로 획득"""
        info = game_info or self._get_game_rect()
        if not info:
            if self.debug:
                print("[MinimapDetector] 게임 창을 찾을 수 없습니다.")
            return None
            
        client_w = info["client_rect"][2]
        client_h = info["client_rect"][3]
        
        scale_x = client_w / self.base_resolution[0]
        scale_y = client_h / self.base_resolution[1]
        
        # 해상도에 맞게 미니맵 좌표와 크기 스케일링
        mx = int(self.minimap_roi["x"] * scale_x)
        my = int(self.minimap_roi["y"] * scale_y)
        mw = int(self.minimap_roi["w"] * scale_x)
        mh = int(self.minimap_roi["h"] * scale_y)
        
        try:
            # bbox: (left, top, right, bottom)
            left = info["client_origin"][0] + mx
            top = info["client_origin"][1] + my
            right = left + mw
            bottom = top + mh
            
            # 크기가 유효하지 않은 비정상적인 bbox 방어
            if right <= left or bottom <= top:
                return None
                
            # 스레드 안전하고 꼬임이 없는 PIL ImageGrab 사용
            pil_img = ImageGrab.grab(bbox=(left, top, right, bottom))
            if pil_img is None or pil_img.size[0] == 0 or pil_img.size[1] == 0:
                return None
                
            # PIL Image (RGB) -> OpenCV Image (BGR)
            minimap_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            # 분석 표준화를 위해 기준 크기(160, 160)로 리사이징
            if mw != 160 or mh != 160:
                minimap_img = cv2.resize(minimap_img, (160, 160), interpolation=cv2.INTER_LINEAR)
                
            return minimap_img
        except Exception as e:
            if self.debug:
                print(f"[MinimapDetector] 미니맵 캡처 중 오류 발생: {e}")
            return None

    def get_passable_mask(self, minimap_img):
        """HSV 색 공간 필터링으로 통행 가능한 구역(밝은 연두색) 검출"""
        if minimap_img is None:
            return None
            
        hsv = cv2.cvtColor(minimap_img, cv2.COLOR_BGR2HSV)
        passable_mask = cv2.inRange(hsv, self.lower_green, self.upper_green)
        return passable_mask

    def rotate_and_scale(self, passable_mask):
        """45도 반시계 방향 회전 변환 및 이소메트릭 축 보정"""
        if passable_mask is None:
            return None
            
        h, w = passable_mask.shape[:2]
        center = (w // 2, h // 2)
        
        # 반시계 방향 45도 회전 (라디안 환산 각도로는 음의 각도)
        # 이소메트릭 격자를 수평/수직 격자로 1:1 보정하기 위한 스케일 다운 (1 / sqrt(2)) 적용
        scale = 1.0 / math.sqrt(2.0)
        M = cv2.getRotationMatrix2D(center, -45, scale)
        
        grid_map = cv2.warpAffine(passable_mask, M, (w, h), flags=cv2.INTER_NEAREST)
        return grid_map

    def get_obstacle_grid(self, downsample_size=None):
        """
        최종 이진화 및 회전된 격자 지도를 반환.
        1: 통행 가능 (Passable)
        0: 장애물 / 미지 영역 (Obstacle)
        
        A* 알고리즘의 효율성을 위해 downsample_size (예: 40, 80)를 지정하면 다운샘플링하여 반환합니다.
        """
        img = self.capture_minimap()
        if img is None:
            return None
            
        mask = self.get_passable_mask(img)
        rotated = self.rotate_and_scale(mask)
        
        if rotated is None:
            return None
            
        # 픽셀 값을 0(장애물)과 1(이동가능)로 이진화
        grid = (rotated > 0).astype(np.uint8)
        
        if downsample_size is not None:
            # INTER_NEAREST를 사용하여 이진 격자 무결성 유지
            grid_resized = cv2.resize(grid, (downsample_size, downsample_size), interpolation=cv2.INTER_NEAREST)
            
            # 저장용 이미지 디버깅을 위해 원본 이미지와 함께 보관
            if self.debug:
                self.save_debug_image(img, mask, rotated, grid_resized)
                
            return grid_resized
            
        if self.debug:
            self.save_debug_image(img, mask, rotated, grid)
            
        return grid

    def save_debug_image(self, original, mask, rotated, grid):
        """디버깅을 위한 미니맵 처리 전과정 시각화 저장"""
        try:
            # grid 맵은 0과 1이므로 시각화를 위해 255를 곱해줌
            grid_vis = (grid * 255).astype(np.uint8)
            grid_vis_resized = cv2.resize(grid_vis, (160, 160), interpolation=cv2.INTER_NEAREST)
            grid_bgr = cv2.cvtColor(grid_vis_resized, cv2.COLOR_GRAY2BGR)
            
            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            rotated_bgr = cv2.cvtColor(rotated, cv2.COLOR_GRAY2BGR)
            
            # 4개 단계를 가로로 병합하여 하나의 이미지로 만듦
            merged = np.hstack((original, mask_bgr, rotated_bgr, grid_bgr))
            
            # 텍스트 오버레이 추가
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(merged, "Original", (10, 20), font, 0.5, (0, 255, 0), 1)
            cv2.putText(merged, "HSV Mask", (170, 20), font, 0.5, (0, 255, 0), 1)
            cv2.putText(merged, "Rotated -45deg", (330, 20), font, 0.5, (0, 255, 0), 1)
            cv2.putText(merged, f"Grid ({grid.shape[0]}x{grid.shape[1]})", (490, 20), font, 0.5, (0, 255, 0), 1)
            
            debug_path = os.path.join(os.path.dirname(__file__), "debug_minimap.png")
            cv2.imwrite(debug_path, merged)
        except Exception as e:
            print(f"[MinimapDetector] 디버그 이미지 저장 중 오류 발생: {e}")

if __name__ == "__main__":
    # 단독 테스트 실행
    print("MinimapDetector 테스트 시작...")
    detector = MinimapDetector(debug=True)
    grid = detector.get_obstacle_grid(downsample_size=40)
    if grid is not None:
        print(f"성공적으로 40x40 격자 맵을 가져왔습니다. 중심점 통행 가능 여부: {grid[20, 20]}")
        print("결과가 debug_minimap.png 에 저장되었습니다.")
    else:
        print("미니맵 검출 실패 (게임이 실행 중이 아닐 수 있습니다.)")
