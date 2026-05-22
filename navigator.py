import time
import math
import random
import threading
import ctypes
import win32gui
import win32api
import win32con
import heapq
import cv2
import numpy as np
import os
from mem_state_reader import MemStateReader
from minimap_detector import MinimapDetector

# DPI Awareness (좌표 정확도 보장)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()


class Navigator:
    """맵좌표 기반 캐릭터 자동 이동 엔진 (이소메트릭 뷰)
    
    이동 원리:
    1. 메모리에서 현재 맵좌표 읽기
    2. 목표와의 맵좌표 차이(dx, dy) 산출
    3. 이소메트릭 변환으로 화면 클릭 좌표 계산
    4. 게임 화면에 클릭 → 캐릭터 이동
    5. 목표 도달까지 반복
    """

    def __init__(self, mem_reader=None):
        self.mem_reader = mem_reader or MemStateReader()
        self.detector = MinimapDetector(debug=True)
        self.running = False
        self.thread = None
        self.on_status = None  # callback(status_str)
        self.stuck_blocks = []  # 스턱 감지 시 일시적으로 주입하는 가상 장애물 목록

        # ── 이소메트릭 타일↔픽셀 변환 비율 ──
        # screen_dx = (map_dx - map_dy) * tile_px_x
        # screen_dy = (map_dx + map_dy) * tile_px_y
        # 기본값: 리니지 클래식 1280×960 표준 이소메트릭 (2:1 비율)
        self.tile_px_x = 24.0
        self.tile_px_y = 12.0
        self.calibrated = False

        # ── 이동 파라미터 ──
        self.arrival_threshold = 3    # 도착 판정 거리 (타일)
        self.click_interval = 2.0     # 클릭 간격 (초)
        self.max_click_offset = 250   # 화면 중앙에서 최대 클릭 거리 (px)

        # ── 상태 ──
        self.status = "대기 중"
        self.target = None
        self.distance = 0.0

    # ─────────────────────────────────────────────
    #  로컬 A* 및 장애물 회피 알고리즘
    # ─────────────────────────────────────────────

    def _a_star(self, grid, start, goal):
        """그리드 맵 기반의 경량화된 A* 경로 탐색 알고리즘
        
        grid: 2D numpy array (1: passable, 0: obstacle)
        start: (x, y) 튜플
        goal: (x, y) 튜플
        """
        h, w = grid.shape
        gx = max(0, min(w - 1, goal[0]))
        gy = max(0, min(h - 1, goal[1]))
        goal = (gx, gy)
        
        sx, sy = start
        if grid[sy, sx] == 0:
            # 시작점이 장애물인 경우 (캐릭터 오차/미니맵 노이즈) 주변에서 가장 가까운 이동 가능 구역 탐색
            found = False
            for r in range(1, 6):
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        nx, ny = sx + dx, sy + dy
                        if 0 <= nx < w and 0 <= ny < h and grid[ny, nx] == 1:
                            start = (nx, ny)
                            sx, sy = nx, ny
                            found = True
                            break
                    if found: break
                if found: break
                
        # 8방향 이동 (대각선 포함)
        neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
        
        # open_set: (f_score, g_score, current_node, parent_node)
        open_set = []
        heapq.heappush(open_set, (0, 0, start, None))
        
        came_from = {}
        g_score = {start: 0}
        
        best_node = start
        best_dist = math.sqrt((start[0] - goal[0])**2 + (start[1] - goal[1])**2)
        
        while open_set:
            _, current_g, current, parent = heapq.heappop(open_set)
            
            if current == goal:
                best_node = current
                break
                
            d = math.sqrt((current[0] - goal[0])**2 + (current[1] - goal[1])**2)
            if d < best_dist:
                best_dist = d
                best_node = current
                
            cx, cy = current
            for dx, dy in neighbors:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h:
                    # 대각선 이동 시 단 1픽셀의 벽이라도 걸쳐있으면 차단 (끼임 원천 봉쇄)
                    if dx != 0 and dy != 0:
                        if grid[cy, cx + dx] == 0 or grid[cy + dy, cx] == 0:
                            continue
                            
                    if grid[ny, nx] == 1:
                        move_cost = 2.5 if (dx != 0 and dy != 0) else 1.0
                        tentative_g = current_g + move_cost
                        
                        neighbor = (nx, ny)
                        if neighbor not in g_score or tentative_g < g_score[neighbor]:
                            g_score[neighbor] = tentative_g
                            # 휴리스틱: 유클리드 거리
                            h_score = math.sqrt((nx - goal[0])**2 + (ny - goal[1])**2)
                            f_score = tentative_g + h_score
                            heapq.heappush(open_set, (f_score, tentative_g, neighbor, current))
                            came_from[neighbor] = current
                            
        # 경로 복원
        path = []
        curr = best_node
        while curr in came_from:
            path.append(curr)
            curr = came_from[curr]
        path.reverse()
        
        return path

    def _is_line_clear(self, grid, x0, y0, x1, y1):
        """두 격자 점 사이의 직선 경로 상에 장애물(0)이 없는지 확인 (Line of Sight)"""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        cx, cy = x0, y0
        while True:
            if not (0 <= cx < 80 and 0 <= cy < 80):
                return False
            if grid[cy, cx] == 0:
                return False
            if cx == x1 and cy == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                cx += sx
            if e2 < dx:
                err += dx
                cy += sy
        return True

    def _draw_debug_path(self, grid, start, goal, path, wp_idx):
        """비주얼 디버깅을 위해 A* 탐색 경로와 웨이포인트를 이미지로 가시화"""
        try:
            # 0/1 그리드를 0/255 그레이스케일로 변환 후 BGR로 변환
            vis = (grid * 255).astype(np.uint8)
            vis_color = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
            
            # 격자 가독성을 위해 4배 확대
            scale = 4
            vis_color = cv2.resize(vis_color, (80 * scale, 80 * scale), interpolation=cv2.INTER_NEAREST)
            
            # A* 경로 선 그리기 (녹색)
            for i in range(len(path) - 1):
                pt1 = (path[i][0] * scale + scale // 2, path[i][1] * scale + scale // 2)
                pt2 = (path[i+1][0] * scale + scale // 2, path[i+1][1] * scale + scale // 2)
                cv2.line(vis_color, pt1, pt2, (0, 255, 0), 2)
                
            # 가상 장애물(stuck_blocks) 그리기 (주황색 X)
            now = time.time()
            for block in self.stuck_blocks:
                if now - block["time"] < 10.0:
                    bx, by = block["pos"]
                    pt1 = (bx * scale, by * scale)
                    pt2 = ((bx + 1) * scale, (by + 1) * scale)
                    pt3 = ((bx + 1) * scale, by * scale)
                    pt4 = (bx * scale, (by + 1) * scale)
                    cv2.line(vis_color, pt1, pt2, (0, 165, 255), 1)
                    cv2.line(vis_color, pt3, pt4, (0, 165, 255), 1)

            # 시작점 그리기 (파란색)
            cv2.circle(vis_color, (start[0] * scale + scale // 2, start[1] * scale + scale // 2), 4, (255, 0, 0), -1)
            
            # 최종 목적지 그리기 (빨간색)
            cv2.circle(vis_color, (goal[0] * scale + scale // 2, goal[1] * scale + scale // 2), 4, (0, 0, 255), -1)
            
            # 조준 웨이포인트 그리기 (노란색)
            if wp_idx < len(path):
                wp = path[wp_idx]
                cv2.circle(vis_color, (wp[0] * scale + scale // 2, wp[1] * scale + scale // 2), 6, (0, 255, 255), 2)
                
            debug_path = os.path.join(os.path.dirname(__file__), "debug_astar.png")
            cv2.imwrite(debug_path, vis_color)
        except Exception:
            pass

    # ─────────────────────────────────────────────
    #  내부 유틸리티
    # ─────────────────────────────────────────────

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

    def _get_game_center(self):
        """게임 화면 중앙(=캐릭터 위치)의 스크린 절대 좌표"""
        hwnd = self._find_game_hwnd()
        if not hwnd:
            return None
        client_rect = win32gui.GetClientRect(hwnd)
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        return (origin[0] + client_rect[2] // 2,
                origin[1] + client_rect[3] // 2)

    def _get_pos(self):
        """메모리에서 현재 맵좌표 (x, y) 튜플 반환"""
        state = self.mem_reader.get_state()
        if not state:
            return None
        coords = state.get("coords", "0, 0")
        parts = coords.split(",")
        try:
            x, y = int(parts[0].strip()), int(parts[1].strip())
            return (x, y) if x > 0 and y > 0 else None
        except (ValueError, IndexError):
            return None

    def _map_delta_to_screen(self, dx, dy):
        """맵좌표 차이 → 이소메트릭 화면 픽셀 오프셋"""
        sx = (dx + dy) * self.tile_px_x
        sy = (dy - dx) * self.tile_px_y
        return (sx, sy)

    def _set_status(self, text):
        self.status = text
        if self.on_status:
            try:
                self.on_status(text)
            except Exception:
                pass

    def _click_game(self, screen_x, screen_y):
        """게임 창에 클릭 전송 (Interception 커널 드라이버 방식 - 안티치트 완벽 우회)
        
        커널 레벨(Ring 0) 필터 드라이버를 통해 물리적인 마우스 하드웨어 신호를 에뮬레이트.
        SendInput이나 PostMessage가 차단되는 강력한 안티치트 환경에서도 
        물리 마우스 입력과 동일하게 취급되어 우회할 수 있음.
        """
        hwnd = self._find_game_hwnd()
        if not hwnd:
            return

        # 1. 게임 창 포커스
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(0.1)

        # 2. Interception으로 물리 레벨 이동 및 클릭 주입
        try:
            import interception
            if not getattr(self, '_interception_initialized', False):
                interception.auto_capture_devices()
                self._interception_initialized = True
            
            interception.move_to(screen_x, screen_y)
            time.sleep(0.08)  # 이동 후 안정성 확보를 위한 짧은 대기
            interception.click()
        except ImportError:
            self._set_status("❌ Interception 모듈 없음!")
            print("[ERR] interception-python 모듈이 설치되지 않았습니다.")

    # ─────────────────────────────────────────────
    #  자동 캘리브레이션
    # ─────────────────────────────────────────────

    def calibrate(self):
        """클릭 후 좌표 변화를 측정하여 타일↔픽셀 비율 자동 산출"""

        def _run():
            self._set_status("📐 캘리브레이션 시작...")

            pos1 = self._get_pos()
            if not pos1:
                self._set_status("❌ 캘리브레이션 실패: 좌표 읽기 불가")
                return

            center = self._get_game_center()
            if not center:
                self._set_status("❌ 캘리브레이션 실패: 게임 창 없음")
                return

            # 화면 우측으로 150px 클릭 (이소메트릭 X축 방향 테스트)
            test_offset = 150
            self._click_game(center[0] + test_offset, center[1])
            self._set_status("📐 이동 대기 (3.5초)...")
            time.sleep(3.5)

            pos2 = self._get_pos()
            if not pos2:
                self._set_status("❌ 캘리브레이션 실패: 이동 후 좌표 불가")
                return

            dx = pos2[0] - pos1[0]
            dy = pos2[1] - pos1[1]

            if abs(dx) + abs(dy) < 1:
                self._set_status("❌ 캘리브레이션 실패: 이동 감지 안됨 (장애물?)")
                return

            # 이소메트릭 역산: test_offset = (dx + dy) * tile_px_x
            iso_x = dx + dy
            if abs(iso_x) > 0:
                self.tile_px_x = abs(test_offset / iso_x)

            # 표준 2:1 이소메트릭 비율 적용
            self.tile_px_y = self.tile_px_x / 2.0
            self.calibrated = True

            self._set_status(
                f"✅ 캘리브레이션 완료! "
                f"{self.tile_px_x:.1f}×{self.tile_px_y:.1f} px/tile "
                f"(Δ{dx},{dy})"
            )

        threading.Thread(target=_run, daemon=True).start()

    # ─────────────────────────────────────────────
    #  이동 제어
    # ─────────────────────────────────────────────

    def move_to(self, target_x, target_y):
        """목표 좌표까지 반복 클릭 이동 시작 (비동기)"""
        self.target = (target_x, target_y)
        self.running = True
        self._set_status(f"🚶 이동 시작 → ({target_x}, {target_y})")

        if self.thread and self.thread.is_alive():
            return  # 기존 스레드가 새 target 자동 인식

        self.thread = threading.Thread(target=self._move_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """이동 중단"""
        self.running = False
        self.target = None
        self._set_status("⏹ 이동 중단")

    def _move_loop(self):
        """반복 클릭으로 목표까지 걸어가는 메인 루프 (당근 기법 적용)
        
        픽셀/타일 비율의 오차로 인한 배회(Wandering)를 막기 위해,
        목표까지의 '방향'만 계산하여 일정 거리(150px) 앞을 계속 클릭하며 쫓아가는 방식입니다.
        """
        stuck_count = 0
        last_pos = None
        last_nx = 0.0
        last_ny = 0.0

        while self.running and self.target:
            try:
                pos = self._get_pos()
                if not pos:
                    self._set_status("⚠ 좌표 읽기 실패, 재시도...")
                    time.sleep(1)
                    continue

                tx, ty = self.target
                dx = tx - pos[0]
                dy = ty - pos[1]
                dist = math.sqrt(dx * dx + dy * dy)
                self.distance = dist

                # ── 도착 판정 ──
                if dist <= self.arrival_threshold:
                    self._set_status(f"✅ 도착! ({pos[0]}, {pos[1]})")
                    self.running = False
                    # 제자리에 멈추도록 캐릭터 발밑(화면 중앙) 클릭
                    center = self._get_game_center()
                    if center:
                        self._click_game(center[0], center[1])
                    break

                # ── 멈춤/막힘 감지 (우회 처리) ──
                if last_pos and last_pos == pos:
                    stuck_count += 1
                    if stuck_count >= 3:
                        self._set_status("⚠ 경로 막힘 → 가상 장애물 주입 및 우회 시도...")
                        # 당시 조준하고 있던 마우스 방향(last_nx, last_ny)을 격자 공간 방향(gnx, gny)으로 역산하여 캐릭터 앞 1~3셀 격자를 가상 장애물로 등록
                        if abs(last_nx) > 0.01 or abs(last_ny) > 0.01:
                            g_dx = last_nx / 4.0 - last_ny / 2.0
                            g_dy = last_nx / 4.0 + last_ny / 2.0
                            g_len = math.sqrt(g_dx**2 + g_dy**2)
                            if g_len > 0:
                                gnx = g_dx / g_len
                                gny = g_dy / g_len
                                
                                # 캐릭터 앞 1~3셀을 가상 장애물로 등록
                                now = time.time()
                                for dist_cell in range(1, 4):
                                    bx = int(40 + gnx * dist_cell)
                                    by = int(40 + gny * dist_cell)
                                    if 0 <= bx < 80 and 0 <= by < 80:
                                        self.stuck_blocks.append({"pos": (bx, by), "time": now})
                                        if self.detector.debug:
                                            print(f"[Navigator] 스턱 감지: 가상 장애물 주입 ({bx}, {by})")
                        
                        # 랜덤 클릭 탈출 보조 로직
                        center = self._get_game_center()
                        if center:
                            # 랜덤한 방향으로 크게 클릭하여 장애물 탈출 (이소메트릭 비율 유지)
                            offset = random.choice([
                                (150, 75), (-150, 75),
                                (150, -75), (-150, -75)
                            ])
                            self._click_game(center[0] + offset[0], center[1] + offset[1])
                            time.sleep(self.click_interval)
                        stuck_count = 0
                        continue
                else:
                    stuck_count = 0
                last_pos = pos

                # ── 이소메트릭 방향 벡터 계산 (A* 우회 또는 Fallback 직선) ──
                vx, vy = None, None
                
                try:
                    # 80x80 크기의 격자 지도를 가져옴 (실시간 비전 분석)
                    grid = self.detector.get_obstacle_grid(downsample_size=80)
                    if grid is not None:
                        grid = grid.copy()
                        now = time.time()
                        
                        # 10초 지난 스턱 블록 만료(Decay) 처리
                        self.stuck_blocks = [b for b in self.stuck_blocks if now - b["time"] < 10.0]
                        
                        # 가상 장애물 주입
                        for block in self.stuck_blocks:
                            bx, by = block["pos"]
                            if 0 <= bx < 80 and 0 <= by < 80:
                                grid[by, bx] = 0
                                
                        # 80x80 격자에서 1셀 = 1.33타일 (160px/80cells = 2px/cell, 1tile = 1.5px)
                        cell_scale = 1.33
                        start_cell = (40, 40)
                        
                        # 반경 26 격자 이내에서 통행 가능(1)하면서 최종 월드 목표(tx, ty)와 가장 가까운 격자 셀을 전역 탐색
                        # 이를 통해 목표 방향이 완전히 가로막혀 있어도, 미니맵 상 안전 통행 지역 중 가장 목표에 가까운 곳을 지정하게 됩니다.
                        best_cell = None
                        min_dist_sq = float('inf')
                        px, py = pos
                        
                        for cy in range(max(0, 40 - 26), min(80, 40 + 27)):
                            for cx in range(max(0, 40 - 26), min(80, 40 + 27)):
                                dist_from_center = math.sqrt((cx - 40)**2 + (cy - 40)**2)
                                if dist_from_center <= 26.0:
                                    if grid[cy, cx] == 1:
                                        # 셀의 월드 좌표 상대 오프셋 산출
                                        w_dx = (cx - 40) * cell_scale
                                        w_dy = (cy - 40) * cell_scale
                                        
                                        # 최종 목표 월드 좌표와의 유클리드 거리 제곱
                                        d_sq = (px + w_dx - tx)**2 + (py + w_dy - ty)**2
                                        if d_sq < min_dist_sq:
                                            min_dist_sq = d_sq
                                            best_cell = (cx, cy)
                                            
                        if best_cell is not None:
                            goal_cell = best_cell
                        else:
                            goal_cell = (40, 40)
                            
                        # A* 경로 산출
                        path = self._a_star(grid, start_cell, goal_cell)
                        
                        if path and len(path) > 1:
                            # 내 위치(40, 40)에서 조준 웨이포인트까지 장애물(0) 없이 훤히 뚫린(Line of Sight) 가장 먼 노드 탐색
                            best_wp_idx = 1
                            for idx in range(2, min(len(path), 6)):  # 최대 5보 앞까지 검사
                                wx, wy = path[idx]
                                if self._is_line_clear(grid, 40, 40, wx, wy):
                                    best_wp_idx = idx
                                else:
                                    break
                            
                            wp_idx = best_wp_idx
                            wx, wy = path[wp_idx]
                            
                            # 웨이포인트 델타
                            g_wp_dx = wx - 40
                            g_wp_dy = wy - 40
                            
                            # 월드 타일 델타로 복원
                            w_wp_dx = g_wp_dx * cell_scale
                            w_wp_dy = g_wp_dy * cell_scale
                            
                            # 리니지 최적화 이소메트릭 벡터 공식 적용
                            vx = (w_wp_dx + w_wp_dy) * 2.0
                            vy = (w_wp_dy - w_wp_dx) * 1.0
                            
                            # 비주얼 디버그 경로 저장
                            self._draw_debug_path(grid, start_cell, goal_cell, path, wp_idx)
                except Exception as e:
                    if self.detector.debug:
                        print(f"[Navigator] A* 우회 탐색 실패, Fallback 직선 주행: {e}")
                        
                # Fallback: A* 실패 시 또는 미니맵을 읽지 못한 경우 기존의 직선 쫓아가기
                if vx is None or vy is None:
                    vx = (dx + dy) * 2.0
                    vy = (dy - dx) * 1.0
                
                # 벡터 정규화 (길이를 1로 만듦)
                v_len = math.sqrt(vx * vx + vy * vy)
                if v_len == 0:
                    continue
                nx = vx / v_len
                ny = vy / v_len

                # ── 당근 기법 (항상 일정 거리 앞을 클릭) ──
                # 거리가 멀 때는 180px 앞을 클릭하여 시원하게 이동
                # 거리가 가까워지면(5타일 이내) 남은 거리에 비례하여 클릭 거리 축소 (정밀 조준)
                click_radius = 180.0
                if dist < 6.0:
                    # 5타일 남았을 때 약 150px, 1타일 남았을 때 약 30px 수준으로 줄어듦
                    click_radius = max(30.0, dist * 25.0)

                sx = nx * click_radius
                sy = ny * click_radius

                center = self._get_game_center()
                if not center:
                    self._set_status("⚠ 게임 창 미발견")
                    time.sleep(1)
                    continue

                click_x = int(center[0] + sx)
                click_y = int(center[1] + sy)

                self._set_status(f"🚶 → ({tx},{ty}) | 남은 거리: {dist:.1f} 타일")
                
                # 방향 저장 (스턱 시 역산용)
                last_nx, last_ny = nx, ny
                
                self._click_game(click_x, click_y)
                
                # 목적지에 가까워지면 클릭 간격을 줄여서 더욱 촘촘하게 방향을 보정
                sleep_time = self.click_interval if dist > 6.0 else 1.0
                time.sleep(sleep_time)

            except Exception as e:
                self._set_status(f"❌ 이동 에러: {e}")
                time.sleep(1)

        self.running = False
