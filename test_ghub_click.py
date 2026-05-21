import time
import win32gui
import ctypes
from ghub_mouse import ghub_mouse

# DPI Awareness
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

def test_ghub_click():
    print("=" * 60)
    print("  로지텍 G-Hub 가상 드라이버 우회 클릭 테스트")
    print("=" * 60)
    
    hwnd = find_game()
    if not hwnd:
        print("[ERR] 게임 창을 찾을 수 없습니다!")
        return
        
    print(f"[OK] 게임 창 발견: HWND {hwnd}")
    
    # 창 포커스
    try:
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.5)
    
    rect = win32gui.GetClientRect(hwnd)
    origin = win32gui.ClientToScreen(hwnd, (0, 0))
    
    # 게임 화면의 우측 하단 임의 영역 좌표 계산 (중앙에서 약간 빗겨난 바닥 타일)
    test_x = origin[0] + rect[2] // 2 + 150
    test_y = origin[1] + rect[3] // 2 + 100
    
    print(f"가상 마우스 이동 대상 스크린 좌표: ({test_x}, {test_y})")
    
    # 1. 마우스 이동
    # 마우스 커서를 게임 상의 목적지로 직접 이동
    import pydirectinput
    pydirectinput.moveTo(test_x, test_y)
    time.sleep(0.2)
    
    print("드라이버 레벨 가상 클릭 신호 전송 시작...")
    # 2. 로지텍 가상 드라이버 신호를 통해 클릭 실행 (안티치트 우회)
    ghub_mouse.click()
    
    print("[OK] 전송 완료! 게임 화면의 캐릭터가 우측 하단으로 이동했는지 확인하세요.")
    print("=" * 60)

if __name__ == "__main__":
    test_ghub_click()
