"""
Inact.dll 후킹 방식 클릭 테스트 스크립트
=========================================
분석 결과 Inact.dll은 이름 없는 3개의 함수(Ordinal 1, 2, 3)를 외부에 노출합니다.
SetWindowsHookExA를 사용해 대상 프로세스에 침투하여 내부에서 메시지를 발생시키는 방식으로
안티치트를 우회하는 것으로 보입니다.

정확한 파라미터는 분석이 더 필요하지만, 가장 일반적인 형태인
- 함수 1: 초기화 / 훅 설치 (파라미터: HWND)
- 함수 2: 클릭 (파라미터: x, y, button_type)
- 함수 3: 해제 / 훅 제거 (파라미터: 없음)
패턴을 가정하고 테스트합니다.
"""
import time
import ctypes
import win32gui
import pydirectinput
import traceback

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
    # 중앙에서 약간 떨어진 좌표를 타겟으로
    return (origin[0] + rect[2] // 2 + 100,
            origin[1] + rect[3] // 2 + 100)

def test_inact_dll():
    dll_path = r"C:\Users\drspi\Downloads\IMax (1)\dll\Inact.dll"
    print(f"[*] DLL 로드 시도: {dll_path}")
    
    try:
        # C 호출 규약 (cdecl) 및 stdcall 규약 두 가지를 시도해볼 수 있습니다.
        # 일반적인 Windows API 훅용 DLL은 WinDLL (stdcall)을 사용합니다.
        inact = ctypes.WinDLL(dll_path)
        print("[OK] DLL 로드 성공")
    except Exception as e:
        print(f"[ERR] DLL 로드 실패: {e}")
        return

    # 함수 포인터 획득 (이름이 없으므로 인덱스(Ordinal)로 접근)
    func1 = inact[1]
    func2 = inact[2]
    func3 = inact[3]

    hwnd = find_game()
    if not hwnd:
        print("[ERR] 게임 창을 찾을 수 없습니다.")
        return
        
    print(f"[OK] 게임 창 발견 (HWND: {hwnd})")
    
    x, y = get_test_coords(hwnd)
    print(f"[INFO] 타겟 좌표: ({x}, {y})")

    # 게임창 포커스
    try:
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except:
        pass
    
    print("\n[INFO] 3초 후 테스트를 시작합니다. 화면을 주시하세요.")
    time.sleep(3)
    
    print("\n[STEP 1] 마우스 커서 이동 (pydirectinput 활용)")
    pydirectinput.moveTo(x, y)
    time.sleep(0.5)

    print("\n[STEP 2] Ordinal 1 호출 (초기화/훅 설치 예상)")
    try:
        # 파라미터가 정확히 무엇인지 모르므로, 
        # HWND (핸들) 값을 넘겨보는 것을 시도합니다.
        res1 = func1(hwnd)
        print(f"  -> 결과: {res1}")
    except Exception as e:
        print(f"  -> 예외 발생: {e}")
        
    time.sleep(0.5)
    
    print("\n[STEP 3] Ordinal 2 호출 (클릭 예상)")
    try:
        # 일반적으로 클릭 함수는 (x, y) 좌표나 (버튼 종류)를 파라미터로 받습니다.
        # 1은 좌클릭으로 가정해봅니다.
        res2 = func2(x, y, 1)
        print(f"  -> 결과(x,y,1): {res2}")
    except Exception as e:
        print(f"  -> 예외 발생: {e}")
        try:
            # 실패 시 파라미터 0개로 단순 호출 시도 (현재 마우스 위치 기준 클릭일 가능성)
            print("  -> 파라미터 없이 호출 시도...")
            res2_alt = func2()
            print(f"  -> 결과(): {res2_alt}")
        except Exception as e2:
            print(f"  -> 예외 발생: {e2}")

    time.sleep(0.5)

    print("\n[STEP 4] Ordinal 3 호출 (해제/훅 제거 예상)")
    try:
        res3 = func3()
        print(f"  -> 결과: {res3}")
    except Exception as e:
        print(f"  -> 예외 발생: {e}")
        
    print("\n테스트 종료. 캐릭터가 이동했는지 확인해주세요.")
    print("만약 파이썬 스크립트가 튕기거나(Crash) 강제종료되었다면, 파라미터 개수나 타입이 맞지 않아서 발생하는 문제일 수 있습니다.")

if __name__ == "__main__":
    test_inact_dll()
