import time
import ctypes
import win32gui
import pydirectinput

def find_game():
    hwnd = win32gui.FindWindow(None, "Lineage Classic")
    if not hwnd:
        hwnds = []
        win32gui.EnumWindows(lambda h, l: l.append(h) if "Lineage" in win32gui.GetWindowText(h) else None, hwnds)
        hwnd = hwnds[0] if hwnds else None
    return hwnd

def get_test_coords(hwnd):
    rect = win32gui.GetClientRect(hwnd)
    origin = win32gui.ClientToScreen(hwnd, (0, 0))
    return (origin[0] + rect[2] // 2 + 100, origin[1] + rect[3] // 2 + 100)

def test_inact_dll_advanced():
    dll_path = r"C:\Users\drspi\Downloads\IMax (1)\dll\Inact.dll"
    inact = ctypes.WinDLL(dll_path)
    func1, func2, func3 = inact[1], inact[2], inact[3]

    hwnd = find_game()
    x, y = get_test_coords(hwnd)
    
    # 클라이언트 상대 좌표로 변환 (비활성 클릭은 대부분 상대 좌표를 사용합니다)
    client_x = x - win32gui.ClientToScreen(hwnd, (0, 0))[0]
    client_y = y - win32gui.ClientToScreen(hwnd, (0, 0))[1]

    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(2)
    pydirectinput.moveTo(x, y)
    time.sleep(0.5)

    print(f"[*] 훅 설치 (HWND: {hwnd})")
    func1(hwnd)
    time.sleep(0.5)

    print("[*] 여러 파라미터 조합으로 클릭 시도...")
    
    # 조합 1: (x, y) 상대좌표
    try:
        print(" -> 시도 1: func2(client_x, client_y)")
        func2(client_x, client_y)
        time.sleep(0.2)
    except: pass

    # 조합 2: 상태값 분리 (Down: 1, Up: 2 또는 0)
    try:
        print(" -> 시도 2: func2(client_x, client_y, 0) / func2(..., 1)")
        func2(client_x, client_y, 0) # Down?
        time.sleep(0.1)
        func2(client_x, client_y, 1) # Up?
        time.sleep(0.2)
    except: pass
    
    # 조합 3: HWND 포함
    try:
        print(" -> 시도 3: func2(hwnd, client_x, client_y)")
        func2(hwnd, client_x, client_y)
        time.sleep(0.2)
    except: pass

    print("[*] 훅 제거")
    func3()
    print("테스트 종료. 이동했는지 확인해주세요.")

if __name__ == "__main__":
    test_inact_dll_advanced()
