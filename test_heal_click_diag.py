"""
힐 스킬 클릭 진단 테스트
========================
4가지 클릭 전송 방식을 순차적으로 테스트하여 
UI 요소(퀵슬롯) 더블클릭이 어떤 방식에서 동작하는지 확인합니다.

방법 A: pydirectinput.moveTo + interception.click()  (현재 heal_caster 방식)
방법 B: interception.move_to + interception.click()  (완전 드라이버 통합 방식)
방법 C: interception.click(x, y, clicks=2)           (좌표 직접 전달 방식)
방법 D: interception.move_to + left_click(clicks=2)  (move_to + 전용 래퍼)

사용법: 관리자 권한 터미널에서 실행
→ 게임 화면에서 퀵슬롯의 힐 아이콘이 더블클릭되는지 관찰
"""
import time
import ctypes
import win32gui
import win32api
import pydirectinput
import cv2
import numpy as np
import mss
import os

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()


def find_game():
    hwnd = win32gui.FindWindow(None, "Lineage Classic")
    if not hwnd:
        hwnds = []
        win32gui.EnumWindows(
            lambda h, l: l.append(h) if "Lineage" in win32gui.GetWindowText(h) else None,
            hwnds
        )
        hwnd = hwnds[0] if hwnds else None
    return hwnd


def find_heal_coords(hwnd):
    """heal_caster.py와 동일한 로직으로 힐 아이콘 절대좌표를 찾아 반환"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    panel_path = os.path.join(base_dir, "resources", "quickslot_panel.png")
    heal_path = os.path.join(base_dir, "resources", "heal_icon.png")

    panel_template = cv2.imread(panel_path)
    heal_template = cv2.imread(heal_path)

    if panel_template is None or heal_template is None:
        print("[ERR] 템플릿 이미지를 로드할 수 없습니다.")
        return None

    client_rect = win32gui.GetClientRect(hwnd)
    origin = win32gui.ClientToScreen(hwnd, (0, 0))
    client_w = client_rect[2]
    client_h = client_rect[3]

    # heal_caster.py와 동일한 mss 캡처
    with mss.mss() as sct:
        monitor = {
            "top": origin[1], "left": origin[0],
            "width": client_w, "height": client_h
        }
        screen = cv2.cvtColor(np.array(sct.grab(monitor)), cv2.COLOR_BGRA2BGR)

    # heal_caster.py와 동일한 해상도 스케일링
    scale_x = client_w / 1280.0
    scale_y = client_h / 960.0

    scaled_panel = panel_template
    scaled_heal = heal_template

    if abs(scale_x - 1.0) > 0.01 or abs(scale_y - 1.0) > 0.01:
        pw = int(panel_template.shape[1] * scale_x)
        ph = int(panel_template.shape[0] * scale_y)
        scaled_panel = cv2.resize(panel_template, (pw, ph), interpolation=cv2.INTER_LINEAR)

        hw = int(heal_template.shape[1] * scale_x)
        hh = int(heal_template.shape[0] * scale_y)
        scaled_heal = cv2.resize(heal_template, (hw, hh), interpolation=cv2.INTER_LINEAR)
        print(f"[INFO] 해상도 스케일링 적용: {scale_x:.2f}x, {scale_y:.2f}y")

    # 패널 매칭
    res_panel = cv2.matchTemplate(screen, scaled_panel, cv2.TM_CCOEFF_NORMED)
    _, max_val_p, _, max_loc_p = cv2.minMaxLoc(res_panel)
    if max_val_p < 0.65:
        print(f"[ERR] 퀵슬롯 패널 매칭 실패 (score={max_val_p:.4f})")
        return None

    px, py = max_loc_p
    pw, ph = scaled_panel.shape[1], scaled_panel.shape[0]
    panel_crop = screen[py:py+ph, px:px+pw]

    # 힐 아이콘 매칭
    res_heal = cv2.matchTemplate(panel_crop, scaled_heal, cv2.TM_CCOEFF_NORMED)
    _, max_val_h, _, max_loc_h = cv2.minMaxLoc(res_heal)
    if max_val_h < 0.65:
        print(f"[ERR] 힐 아이콘 매칭 실패 (score={max_val_h:.4f})")
        return None

    hx, hy = max_loc_h
    hw_w, hw_h = scaled_heal.shape[1], scaled_heal.shape[0]

    heal_x = origin[0] + px + hx + hw_w // 2
    heal_y = origin[1] + py + hy + hw_h // 2

    # 캐릭터 중앙 (하단 정보패널을 제외한 실 게임화면의 중앙)
    center_x = origin[0] + client_w // 2
    center_y = origin[1] + py // 2

    print(f"[OK] 패널: ({px},{py}) score={max_val_p:.4f}")
    print(f"[OK] 힐 아이콘: ({hx},{hy}) in panel, score={max_val_h:.4f}")
    print(f"[OK] 힐 절대좌표: ({heal_x}, {heal_y})")
    print(f"[OK] 캐릭터 중앙: ({center_x}, {center_y})")
    return heal_x, heal_y, center_x, center_y


def wait_and_focus(hwnd, label, seconds=5):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  {seconds}초 후 실행... 게임 화면을 보세요!")
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(seconds)


def test_method_A(hwnd, heal_x, heal_y, center_x, center_y):
    """방법 A: pydirectinput.moveTo + interception.click() (현재 방식)"""
    wait_and_focus(hwnd, "방법 A: pydirectinput.moveTo + interception.click()")
    import interception

    print(f"  [1] 힐 아이콘으로 이동: ({heal_x}, {heal_y})")
    pydirectinput.moveTo(heal_x, heal_y)
    pos = win32api.GetCursorPos()
    print(f"      moveTo 후 커서: {pos}")
    time.sleep(0.25)

    interception.click()
    pos = win32api.GetCursorPos()
    print(f"      click() 1회 후 커서: {pos}")
    time.sleep(0.15)

    interception.click()
    pos = win32api.GetCursorPos()
    print(f"      click() 2회 후 커서: {pos}")
    time.sleep(0.4)

    print(f"  [2] 캐릭터 중앙으로 이동: ({center_x}, {center_y})")
    pydirectinput.moveTo(center_x, center_y)
    pos = win32api.GetCursorPos()
    print(f"      moveTo 후 커서: {pos}")
    time.sleep(0.25)

    interception.click()
    pos = win32api.GetCursorPos()
    print(f"      click() 후 최종 커서: {pos}")
    print("  → 힐이 시전되었나요?")


def test_method_B(hwnd, heal_x, heal_y, center_x, center_y):
    """방법 B: interception.move_to + interception.click() (완전 드라이버 통합)"""
    wait_and_focus(hwnd, "방법 B: interception.move_to + interception.click()")
    import interception

    print(f"  [1] 힐 아이콘으로 이동 (interception.move_to): ({heal_x}, {heal_y})")
    interception.move_to(heal_x, heal_y)
    pos = win32api.GetCursorPos()
    print(f"      move_to 후 커서: {pos}")
    time.sleep(0.25)

    interception.click()
    pos = win32api.GetCursorPos()
    print(f"      click() 1회 후 커서: {pos}")
    time.sleep(0.15)

    interception.click()
    pos = win32api.GetCursorPos()
    print(f"      click() 2회 후 커서: {pos}")
    time.sleep(0.4)

    print(f"  [2] 캐릭터 중앙으로 이동 (interception.move_to): ({center_x}, {center_y})")
    interception.move_to(center_x, center_y)
    pos = win32api.GetCursorPos()
    print(f"      move_to 후 커서: {pos}")
    time.sleep(0.25)

    interception.click()
    pos = win32api.GetCursorPos()
    print(f"      click() 후 최종 커서: {pos}")
    print("  → 힐이 시전되었나요?")


def test_method_C(hwnd, heal_x, heal_y, center_x, center_y):
    """방법 C: interception.click(x, y, clicks=2) (좌표 직접 전달)"""
    wait_and_focus(hwnd, "방법 C: interception.click(x, y, clicks=2)")
    import interception

    print(f"  [1] 힐 아이콘 더블클릭 (interception.click(x,y,clicks=2))")
    interception.click(heal_x, heal_y, clicks=2, interval=0.15, delay=0.25)
    pos = win32api.GetCursorPos()
    print(f"      더블클릭 후 커서: {pos}")
    time.sleep(0.4)

    print(f"  [2] 캐릭터 중앙 클릭 (interception.click(x,y))")
    interception.click(center_x, center_y, delay=0.25)
    pos = win32api.GetCursorPos()
    print(f"      클릭 후 커서: {pos}")
    print("  → 힐이 시전되었나요?")


def test_method_D(hwnd, heal_x, heal_y, center_x, center_y):
    """방법 D: interception.move_to + left_click(clicks=2)"""
    wait_and_focus(hwnd, "방법 D: interception.move_to + left_click(clicks=2)")
    import interception

    print(f"  [1] 힐 아이콘으로 이동 (interception.move_to): ({heal_x}, {heal_y})")
    interception.move_to(heal_x, heal_y)
    pos = win32api.GetCursorPos()
    print(f"      move_to 후 커서: {pos}")
    time.sleep(0.25)

    interception.left_click(clicks=2, interval=0.15)
    pos = win32api.GetCursorPos()
    print(f"      left_click(clicks=2) 후 커서: {pos}")
    time.sleep(0.4)

    print(f"  [2] 캐릭터 중앙으로 이동 (interception.move_to): ({center_x}, {center_y})")
    interception.move_to(center_x, center_y)
    pos = win32api.GetCursorPos()
    print(f"      move_to 후 커서: {pos}")
    time.sleep(0.25)

    interception.left_click()
    pos = win32api.GetCursorPos()
    print(f"      left_click() 후 최종 커서: {pos}")
    print("  → 힐이 시전되었나요?")


def main():
    print("=" * 60)
    print("  힐 스킬 클릭 진단 테스트")
    print("=" * 60)

    hwnd = find_game()
    if not hwnd:
        print("[ERR] 게임 창 발견 실패!")
        return

    title = win32gui.GetWindowText(hwnd)
    print(f"[OK] 게임 창: '{title}' (HWND: {hwnd})")

    # 화면 캡처 및 좌표 찾기를 먼저 수행 (interception 초기화 전)
    coords = find_heal_coords(hwnd)
    if not coords:
        return
    heal_x, heal_y, center_x, center_y = coords

    # interception 초기화
    import interception
    interception.auto_capture_devices()
    print("[OK] Interception 디바이스 캡처 완료")

    # 방법 A: 현재 heal_caster 방식
    test_method_A(hwnd, heal_x, heal_y, center_x, center_y)
    time.sleep(6)

    # 방법 B: 완전 드라이버 통합
    test_method_B(hwnd, heal_x, heal_y, center_x, center_y)
    time.sleep(6)

    # 방법 C: 좌표 직접 전달
    test_method_C(hwnd, heal_x, heal_y, center_x, center_y)
    time.sleep(6)

    # 방법 D: move_to + left_click
    test_method_D(hwnd, heal_x, heal_y, center_x, center_y)

    print()
    print("=" * 60)
    print("  테스트 완료!")
    print("=" * 60)
    print()
    print("각 방법에서 힐이 시전되었는지 알려주세요:")
    print("  방법 A: pydirectinput.moveTo + interception.click()")
    print("  방법 B: interception.move_to + interception.click()")
    print("  방법 C: interception.click(x, y, clicks=2)")
    print("  방법 D: interception.move_to + left_click(clicks=2)")
    print()
    print("  또한 각 단계에서 커서 좌표가 변했는지도 확인해주세요!")


if __name__ == "__main__":
    main()
