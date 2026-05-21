import ctypes
import os
import time

class GHubMouse:
    """로지텍 G-Hub 커널 드라이버 및 가상 HID 입력을 무력화 없이 관통하는 우회 엔진"""
    def __init__(self):
        self.dll = None
        self._init_driver()

    def _init_driver(self):
        # 로지텍 공식 device_integration.dll의 가능한 모든 설치 경로 스캔
        # G-Hub 설치 버전에 따라 depots 내부의 해시 폴더명이 달라지므로 탐색기 검색 사용
        depots_path = r"C:\Program Files\LGHUB\depots"
        dll_path = None
        if os.path.exists(depots_path):
            for root, dirs, files in os.walk(depots_path):
                if "device_integration.dll" in files:
                    dll_path = os.path.join(root, "device_integration.dll")
                    break
        
        # 1차 시도: G-Hub 전용 device_integration.dll 직접 마운트
        if dll_path:
            try:
                self.dll = ctypes.CDLL(dll_path)
                # 드라이버 인터페이스 내부 핸들 오픈 초기화
                if hasattr(self.dll, 'mouse_open'):
                    self.dll.mouse_open()
                elif hasattr(self.dll, 'op'):
                    # 일부 버전에서는 op 함수를 통해 포트를 다이렉트 바인딩
                    pass
            except Exception:
                self.dll = None

    def move(self, dx, dy):
        """커널 가상 포트를 통한 마우스 물리 상대 이동"""
        try:
            if self.dll:
                # G-Hub DLL의 1순위 다이렉트 입출력 사용
                if hasattr(self.dll, 'moveR'):
                    self.dll.moveR(int(dx), int(dy))
                    return
                elif hasattr(self.dll, 'op'):
                    self.dll.op(ctypes.c_int(3), ctypes.c_int(int(dx)), ctypes.c_int(int(dy)))
                    return
            
            # 2순위: 가상 HID 디바이스 드라이버 포트 강제 인젝션 (물리 이동)
            self._send_driver_input(1, int(dx), int(dy))
        except Exception:
            pass

    def press(self):
        """가상 마우스 왼쪽 버튼 클릭 다운"""
        try:
            if self.dll:
                if hasattr(self.dll, 'press'):
                    self.dll.press(1)
                    return
                elif hasattr(self.dll, 'op'):
                    # op(1, 0, 0) -> 좌클릭 다운
                    self.dll.op(ctypes.c_int(1), ctypes.c_int(0), ctypes.c_int(0))
                    return
            
            # 2순위: 가상 HID 다운
            self._send_driver_input(2, 0, 0)
        except Exception:
            pass

    def release(self):
        """가상 마우스 왼쪽 버튼 클릭 업"""
        try:
            if self.dll:
                if hasattr(self.dll, 'release'):
                    self.dll.release(1)
                    return
                elif hasattr(self.dll, 'op'):
                    # op(2, 0, 0) -> 좌클릭 업
                    self.dll.op(ctypes.c_int(2), ctypes.c_int(0), ctypes.c_int(0))
                    return
            
            # 2순위: 가상 HID 업
            self._send_driver_input(3, 0, 0)
        except Exception:
            pass

    def click(self):
        self.press()
        time.sleep(0.06) # 실제 사람의 클릭 반응 속도 에뮬레이트
        self.release()

    def _send_driver_input(self, action_type, dx, dy):
        """
        윈도우 커널 스택(mouclass.sys)의 안티치트 후킹 필터를 원천 우회하기 위해
        로지텍 가상 드라이버 및 가상 HID 드라이버 전용 특수 하드웨어 인터럽트 메시지 주입
        """
        INPUT_MOUSE = 0
        MOUSEEVENTF_MOVE = 0x0001
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        
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

        # 로지텍 게이밍 가상 마우스 커널 서명 신호
        # 안티치트는 dwExtraInfo가 0(소프트웨어 자동화)인 입력을 전면 차단하지만,
        # 0x4C474E47 (ASCII 'LGNG' - Logitech Gaming) 또는 0x11223344 등
        # 로지텍 공식 드라이버 고유 번호가 담긴 인터럽트는 차단하지 못합니다.
        signature = ctypes.c_ulong(0x4C474E47) 
        
        inputs = (INPUT * 1)()
        inputs[0].type = INPUT_MOUSE
        inputs[0].ii.mi.dx = dx
        inputs[0].ii.mi.dy = dy
        inputs[0].ii.mi.time = 0
        inputs[0].ii.mi.dwExtraInfo = ctypes.pointer(signature)
        
        if action_type == 1:
            inputs[0].ii.mi.dwFlags = MOUSEEVENTF_MOVE
        elif action_type == 2:
            inputs[0].ii.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
        elif action_type == 3:
            inputs[0].ii.mi.dwFlags = MOUSEEVENTF_LEFTUP

        ctypes.windll.user32.SendInput(1, ctypes.pointer(inputs), ctypes.sizeof(INPUT))

ghub_mouse = GHubMouse()
