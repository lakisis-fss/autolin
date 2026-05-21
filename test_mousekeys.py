"""
Windows 접근성 '마우스 키(Mouse Keys)' 우회 클릭 테스트
======================================================
키보드 입력은 안티치트가 허용하므로,
Numpad 5 키를 마우스 좌클릭으로 변환하는 Windows 접근성 기능을 활용합니다.

사전 조건: Windows 마우스 키 기능 활성화 필요
  → 설정 > 접근성 > 마우스 > '마우스 키' 켜기
  → 또는 좌Alt + 좌Shift + NumLock 동시 누르기
"""
import time
import ctypes
import ctypes.wintypes
import win32gui
import pydirectinput

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()


def enable_mouse_keys():
    """Windows 마우스 키 기능을 프로그래밍 방식으로 활성화"""
    
    class MOUSEKEYS(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("dwFlags", ctypes.c_uint),
            ("iMaxSpeed", ctypes.c_uint),
            ("iTimeToMaxSpeed", ctypes.c_uint),
            ("iCtrlSpeed", ctypes.c_uint),
            ("dwReserved1", ctypes.c_uint),
            ("dwReserved2", ctypes.c_uint),
        ]

    SPI_SETMOUSEKEYS = 0x0037
    SPI_GETMOUSEKEYS = 0x0036
    SPIF_SENDCHANGE = 0x0002
    MKF_MOUSEKEYSON = 0x00000001
    MKF_AVAILABLE = 0x00000002

    mk = MOUSEKEYS()
    mk.cbSize = ctypes.sizeof(MOUSEKEYS)

    # 현재 상태 확인
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETMOUSEKEYS, ctypes.sizeof(MOUSEKEYS), ctypes.byref(mk), 0)
    
    if mk.dwFlags & MKF_MOUSEKEYSON:
        print("[OK] 마우스 키가 이미 활성화되어 있습니다.")
        return True

    # 활성화
    mk.dwFlags = MKF_MOUSEKEYSON | MKF_AVAILABLE
    mk.iMaxSpeed = 40
    mk.iTimeToMaxSpeed = 3000
    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETMOUSEKEYS, ctypes.sizeof(MOUSEKEYS), ctypes.byref(mk), SPIF_SENDCHANGE
    )
    
    if result:
        print("[OK] 마우스 키를 프로그래밍 방식으로 활성화했습니다!")
        return True
    else:
        print("[WARN] 프로그래밍 활성화 실패. 수동으로 켜주세요:")
        print("       좌Alt + 좌Shift + NumLock 동시 누르기")
        return False


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


def test_mousekeys_click():
    print("=" * 60)
    print("  Windows 마우스 키 우회 클릭 테스트")
    print("=" * 60)

    # 1. 마우스 키 활성화
    enable_mouse_keys()
    time.sleep(0.5)

    # 2. 게임 찾기
    hwnd = find_game()
    if not hwnd:
        print("[ERR] 게임 창을 찾을 수 없습니다!")
        return

    print(f"[OK] 게임 창 발견: HWND {hwnd}")

    # 3. 게임 중앙에서 오프셋 좌표 계산
    rect = win32gui.GetClientRect(hwnd)
    origin = win32gui.ClientToScreen(hwnd, (0, 0))
    test_x = origin[0] + rect[2] // 2 + 120
    test_y = origin[1] + rect[3] // 2 + 80

    # 4. 게임 포커스
    try:
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass

    print(f"[INFO] 5초 후 클릭 테스트... 게임 화면을 보세요!")
    print(f"[INFO] 클릭 좌표: ({test_x}, {test_y})")
    time.sleep(5)

    # 5. 마우스 이동 (이건 안티치트 허용)
    print("[STEP 1] 마우스 커서 이동 중...")
    pydirectinput.moveTo(test_x, test_y)
    time.sleep(0.3)

    # 6. Numpad 5 (마우스 키 → 좌클릭 변환)
    # NumLock이 꺼져 있어야 마우스 키가 작동함
    # 먼저 NumLock을 끄기
    import ctypes
    VK_NUMLOCK = 0x90
    numlock_state = ctypes.windll.user32.GetKeyState(VK_NUMLOCK) & 1
    if numlock_state:
        print("[STEP 2] NumLock OFF (마우스 키 모드 전환)...")
        pydirectinput.press('numlock')
        time.sleep(0.2)

    print("[STEP 3] Numpad 5 전송 (마우스 키 좌클릭)...")
    pydirectinput.press('numpad5')
    time.sleep(0.5)

    print()
    print("=" * 60)
    print("  캐릭터가 이동했나요?")
    print("=" * 60)
    print()
    print("  ✅ 이동함 → 마우스 키 우회 성공! navigator.py에 적용합니다.")
    print("  ❌ 이동 안 함 → 다른 방법 검토 필요")


if __name__ == "__main__":
    test_mousekeys_click()
