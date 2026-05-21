"""
마우스 클릭 안티치트 우회 - 고급 기법 테스트
============================================
기존 5가지 방법(SendInput, PostMessage, mouse_event, 수동SendInput, SendMessage) 모두 실패.
아래 2가지 새로운 기법을 테스트합니다:

  방법 A: win32u.dll NtUserSendInput 직접 호출 (user32.dll 훅 우회)
  방법 B: Interception 커널 드라이버 (하드웨어 레벨 입력 주입)
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


# ── 공통 구조체 정의 ──
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
    rect = win32gui.GetClientRect(hwnd)
    origin = win32gui.ClientToScreen(hwnd, (0, 0))
    return (origin[0] + rect[2] // 2 + 120,
            origin[1] + rect[3] // 2 + 80)


def wait_and_focus(hwnd, label, seconds=5):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  {seconds}초 후 클릭 전송... 게임 화면을 보세요!")
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(seconds)


# ═══════════════════════════════════════════════════════
#  방법 A: win32u.dll NtUserSendInput 직접 호출
#  user32.dll!SendInput 을 거치지 않고 win32u.dll의
#  NtUserSendInput을 직접 호출하여 user32 훅을 우회
# ═══════════════════════════════════════════════════════
def test_method_A(hwnd, x, y):
    wait_and_focus(hwnd, "방법 A: win32u.dll NtUserSendInput 직접 호출")
    
    try:
        # win32u.dll 로드 및 NtUserSendInput 주소 획득
        k32 = ctypes.windll.kernel32
        
        # win32u.dll이 이미 로드되어 있으면 GetModuleHandle, 아니면 LoadLibrary
        h_win32u = k32.GetModuleHandleW("win32u.dll")
        if not h_win32u:
            h_win32u = k32.LoadLibraryW("win32u.dll")
        
        if not h_win32u:
            print("  [ERR] win32u.dll 로드 실패")
            return
        
        # NtUserSendInput 함수 포인터 획득
        proc_addr = k32.GetProcAddress(h_win32u, b"NtUserSendInput")
        if not proc_addr:
            print("  [ERR] NtUserSendInput 함수를 찾을 수 없음")
            return
        
        # 함수 프로토타입 정의: UINT NtUserSendInput(UINT, LPINPUT, int)
        NtUserSendInput = ctypes.WINFUNCTYPE(
            ctypes.c_uint,        # return: UINT
            ctypes.c_uint,        # nInputs
            ctypes.POINTER(INPUT), # pInputs
            ctypes.c_int           # cbSize
        )(proc_addr)
        
        print(f"  [OK] NtUserSendInput 주소: 0x{proc_addr:X}")
        
        # 마우스 이동 (안티치트 허용)
        pydirectinput.moveTo(x, y)
        time.sleep(0.1)
        
        # 클릭 다운
        extra = ctypes.c_ulong(0)
        inp_down = INPUT()
        inp_down.type = 0  # INPUT_MOUSE
        inp_down.ii.mi.dwFlags = 0x0002  # MOUSEEVENTF_LEFTDOWN
        inp_down.ii.mi.dwExtraInfo = ctypes.pointer(extra)
        
        result1 = NtUserSendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
        time.sleep(0.05)
        
        # 클릭 업
        extra2 = ctypes.c_ulong(0)
        inp_up = INPUT()
        inp_up.type = 0
        inp_up.ii.mi.dwFlags = 0x0004  # MOUSEEVENTF_LEFTUP
        inp_up.ii.mi.dwExtraInfo = ctypes.pointer(extra2)
        
        result2 = NtUserSendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
        
        print(f"  [OK] NtUserSendInput 호출 결과: down={result1}, up={result2}")
        print("  → 전송 완료! 캐릭터 이동을 확인하세요.")
        
    except Exception as e:
        print(f"  [ERR] 방법 A 실패: {e}")


# ═══════════════════════════════════════════════════════
#  방법 B: Interception 커널 드라이버
#  커널 레벨 필터 드라이버로 물리 하드웨어 입력을 에뮬레이트
#  (사전 설치 필요: pip install interception-python)
# ═══════════════════════════════════════════════════════
def test_method_B(hwnd, x, y):
    wait_and_focus(hwnd, "방법 B: Interception 커널 드라이버")
    
    try:
        import interception
        print("  [OK] interception 모듈 로드 성공!")
        
        # 디바이스 자동 감지
        interception.auto_capture_devices()
        time.sleep(0.3)
        
        # 마우스 이동 (pydirectinput 사용)
        pydirectinput.moveTo(x, y)
        time.sleep(0.1)
        
        # Interception을 통한 클릭 (하드웨어 레벨)
        interception.click()
        
        print("  → 전송 완료! 캐릭터 이동을 확인하세요.")
        
    except ImportError:
        print("  [SKIP] interception-python 미설치")
        print("         설치 방법:")
        print("         1. pip install interception-python")
        print("         2. Interception 드라이버 설치 (재부팅 필요)")
        print("            → https://github.com/oblitum/Interception/releases")
    except Exception as e:
        print(f"  [ERR] 방법 B 실패: {e}")


def main():
    print("=" * 60)
    print("  마우스 클릭 안티치트 우회 - 고급 기법 테스트")
    print("=" * 60)

    hwnd = find_game()
    if not hwnd:
        print("[ERR] 게임 창을 찾을 수 없습니다!")
        return

    title = win32gui.GetWindowText(hwnd)
    print(f"[OK] 게임 창: '{title}' (HWND: {hwnd})")

    x, y = get_test_coords(hwnd)
    print(f"[OK] 클릭 좌표: ({x}, {y})")

    # ── 방법 A: NtUserSendInput ──
    test_method_A(hwnd, x, y)
    time.sleep(5)

    # ── 방법 B: Interception ──
    test_method_B(hwnd, x, y)
    time.sleep(3)

    print()
    print("=" * 60)
    print("  테스트 완료!")
    print("=" * 60)
    print()
    print("  방법 A (NtUserSendInput): 캐릭터 이동했나요?")
    print("  방법 B (Interception):    캐릭터 이동했나요?")
    print()
    print("  둘 다 실패 시 → 아두이노 하드웨어 방식만 남습니다.")


if __name__ == "__main__":
    main()
