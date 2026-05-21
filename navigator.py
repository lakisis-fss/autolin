import time
import math
import random
import threading
import ctypes
import win32gui
import win32api
import win32con
import pydirectinput
from mem_state_reader import MemStateReader

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
        self.running = False
        self.thread = None
        self.on_status = None  # callback(status_str)

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
        sx = (dx - dy) * self.tile_px_x
        sy = (dx + dy) * self.tile_px_y
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

        # 2. 마우스 커서 이동 (SendInput - 안티치트 허용)
        pydirectinput.moveTo(screen_x, screen_y)
        time.sleep(0.05)

        # 3. Interception으로 물리 레벨 클릭 주입
        try:
            import interception
            if not getattr(self, '_interception_initialized', False):
                interception.auto_capture_devices()
                self._interception_initialized = True
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

            # 이소메트릭 역산: test_offset = (dx - dy) * tile_px_x
            iso_x = dx - dy
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
                        self._set_status("⚠ 경로 막힘 → 우회 시도...")
                        center = self._get_game_center()
                        if center:
                            # 랜덤한 방향으로 크게 클릭하여 장애물 탈출
                            offset = random.choice([
                                (180, 90), (-180, 90),
                                (180, -90), (-180, -90)
                            ])
                            self._click_game(center[0] + offset[0], center[1] + offset[1])
                            time.sleep(self.click_interval)
                        stuck_count = 0
                        continue
                else:
                    stuck_count = 0
                last_pos = pos

                # ── 이소메트릭 방향 벡터 계산 ──
                # 타일 차이를 화면 비율(2:1)에 맞게 벡터로 변환
                vx = (dx - dy) * 2.0
                vy = (dx + dy) * 1.0
                
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
                self._click_game(click_x, click_y)
                
                # 목적지에 가까워지면 클릭 간격을 줄여서 더욱 촘촘하게 방향을 보정
                sleep_time = self.click_interval if dist > 6.0 else 1.0
                time.sleep(sleep_time)

            except Exception as e:
                self._set_status(f"❌ 이동 에러: {e}")
                time.sleep(1)

        self.running = False
