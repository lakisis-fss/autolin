"""
리니지 클래식 마우스 클릭 방식 진단 테스트
============================================
4가지 클릭 전송 방법을 순차적으로 시도하여 어떤 것이 동작하는지 확인합니다.

사용법: 관리자 권한 터미널에서 실행 → 게임 화면을 보면서 캐릭터가 움직이는지 확인
"""
import time
import ctypes
import ctypes.wintypes
import win32gui
import win32api
import win32con
import pydirectinput

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


def get_test_coords(hwnd):
    """게임 중앙에서 오른쪽 아래로 100px 오프셋 좌표 반환"""
    rect = win32gui.GetClientRect(hwnd)
    origin = win32gui.ClientToScreen(hwnd, (0, 0))
    cx = origin[0] + rect[2] // 2 + 100
    cy = origin[1] + rect[3] // 2 + 50
    return cx, cy


def wait_and_focus(hwnd, label, seconds=4):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  {seconds}초 후 클릭 전송... 게임 화면을 보세요!")
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(seconds)


# ── 방법 1: pydirectinput.click (SendInput 표준) ──
def test_method_1(hwnd, x, y):
    wait_and_focus(hwnd, "방법 1: pydirectinput.click() [SendInput]")
    pydirectinput.click(x, y)
    print("  → 전송 완료!")


# ── 방법 2: PostMessage (윈도우 메시지 큐 직접 주입) ──
def test_method_2(hwnd, x, y):
    wait_and_focus(hwnd, "방법 2: PostMessage [WM_LBUTTONDOWN/UP]")
    pydirectinput.moveTo(x, y)
    time.sleep(0.05)
    client_x, client_y = win32gui.ScreenToClient(hwnd, (x, y))
    lparam = win32api.MAKELONG(client_x, client_y)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(0.05)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    print("  → 전송 완료!")


# ── 방법 3: mouse_event (구형 API, SendInput 이전 세대) ──
def test_method_3(hwnd, x, y):
    wait_and_focus(hwnd, "방법 3: mouse_event() [구형 API]")
    pydirectinput.moveTo(x, y)
    time.sleep(0.05)
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    print("  → 전송 완료!")


# ── 방법 4: SendInput 수동구성 (이동+클릭 원자적 결합) ──
def test_method_4(hwnd, x, y):
    wait_and_focus(hwnd, "방법 4: SendInput 수동구성 [이동+클릭 원자적 결합]")

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
        ]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_ulong),
            ("ii", INPUT_UNION)
        ]

    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    abs_x = int(x * 65536 / screen_w)
    abs_y = int(y * 65536 / screen_h)
    extra = ctypes.c_ulong(0)

    ABSOLUTE = 0x8000
    MOVE = 0x0001
    LEFTDOWN = 0x0002
    LEFTUP = 0x0004

    # 3개 이벤트를 하나의 SendInput 호출로 원자적 전송
    inputs = (INPUT * 3)()
    inputs[0].type = 0
    inputs[0].ii.mi.dx = abs_x
    inputs[0].ii.mi.dy = abs_y
    inputs[0].ii.mi.dwFlags = ABSOLUTE | MOVE
    inputs[0].ii.mi.dwExtraInfo = ctypes.pointer(extra)

    inputs[1].type = 0
    inputs[1].ii.mi.dwFlags = LEFTDOWN
    inputs[1].ii.mi.dwExtraInfo = ctypes.pointer(extra)

    inputs[2].type = 0
    inputs[2].ii.mi.dwFlags = LEFTUP
    inputs[2].ii.mi.dwExtraInfo = ctypes.pointer(extra)

    ctypes.windll.user32.SendInput(3, ctypes.pointer(inputs), ctypes.sizeof(INPUT))
    print("  → 전송 완료!")


# ── 방법 5: SendMessage (동기식 윈도우 메시지) ──
def test_method_5(hwnd, x, y):
    wait_and_focus(hwnd, "방법 5: SendMessage [동기식 윈도우 메시지]")
    pydirectinput.moveTo(x, y)
    time.sleep(0.05)
    client_x, client_y = win32gui.ScreenToClient(hwnd, (x, y))
    lparam = win32api.MAKELONG(client_x, client_y)
    win32api.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(0.05)
    win32api.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    print("  → 전송 완료!")


def main():
    print("=" * 60)
    print("  리니지 클래식 마우스 클릭 진단 테스트")
    print("=" * 60)

    hwnd = find_game()
    if not hwnd:
        print("[ERROR] 게임 창을 찾을 수 없습니다!")
        return

    title = win32gui.GetWindowText(hwnd)
    print(f"[OK] 게임 창 발견: '{title}' (HWND: {hwnd})")

    x, y = get_test_coords(hwnd)
    print(f"[OK] 클릭 테스트 좌표: ({x}, {y})")
    print()
    print("각 방법 사이에 5초간 대기합니다.")
    print("게임 화면을 보면서 캐릭터가 움직이는지 확인하세요!")
    print("(어떤 방법에서 캐릭이 움직였는지 기억해주세요)")

    test_method_1(hwnd, x, y)
    time.sleep(5)

    test_method_2(hwnd, x, y)
    time.sleep(5)

    test_method_3(hwnd, x, y)
    time.sleep(5)

    test_method_4(hwnd, x, y)
    time.sleep(5)

    test_method_5(hwnd, x, y)
    time.sleep(3)

    print()
    print("=" * 60)
    print("  테스트 완료!")
    print("=" * 60)
    print()
    print("결과를 알려주세요:")
    print("  방법 1: pydirectinput.click (SendInput)")
    print("  방법 2: PostMessage")
    print("  방법 3: mouse_event (구형 API)")
    print("  방법 4: SendInput 수동구성 (원자적)")
    print("  방법 5: SendMessage (동기식)")
    print()
    print("  → 모두 안 되면 커널 레벨 드라이버(Interception)가 필요합니다.")


if __name__ == "__main__":
    main()
