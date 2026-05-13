import os
import time
import win32api
import win32con
import mss
import cv2
import numpy as np
import tkinter as tk
import ctypes

# 고해상도(DPI) 디스플레이에서 캡처 좌표가 틀어지는 현상 방지
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

# === 설정 ===
OUTPUT_DIR = "datasets/images"
CAPTURE_KEY = win32con.VK_F12  # F12 키로 토글
COOLDOWN = 0.2                 # 캡처 간격(초)
TARGET_WIDTH = 800             # 모델 학습용 고정 너비 (4:3 비율)
TARGET_HEIGHT = 600            # 모델 학습용 고정 높이

class CaptureOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Dataset Area Selector")
        self.root.geometry("800x600+100+100")
        
        # 윈도우 투명색 지정 (마젠타 색상을 완전히 투명하게 렌더링)
        self.root.attributes("-transparentcolor", "magenta")
        self.root.attributes("-topmost", True)
        self.root.config(bg="magenta")
        
        # 테두리 역할을 할 프레임
        self.frame = tk.Frame(self.root, bg="magenta", highlightbackground="red", highlightthickness=3)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # 상태 안내 텍스트
        self.info_label = tk.Label(self.frame, 
                                   text="[F12] 캡처 대기 중\n1. 이 창을 드래그/리사이즈하여 유튜브 영상의 '순수 게임 화면'에 딱 맞추세요.\n2. 스트리머 캠이나 채팅창은 테두리 밖으로 빼세요.", 
                                   bg="red", fg="white", font=("맑은 고딕", 10, "bold"), justify=tk.LEFT)
        self.info_label.pack(side=tk.TOP, anchor=tk.NW)

        self.is_capturing = False
        self.was_key_pressed = False
        self.last_capture_time = 0
        
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
            
        # 50ms마다 키보드 입력 확인 및 캡처 처리
        self.root.after(50, self.capture_loop)
        
    def capture_loop(self):
        is_key_pressed = (win32api.GetAsyncKeyState(CAPTURE_KEY) & 0x8000) != 0
        
        if is_key_pressed and not self.was_key_pressed:
            self.is_capturing = not self.is_capturing
            if self.is_capturing:
                self.info_label.config(text="[REC] 캡처 진행 중... (중지하려면 F12)", bg="lime", fg="black")
                print(f"\n[+] 연속 캡처 시작 ({COOLDOWN}초 간격)")
            else:
                self.info_label.config(text="[F12] 캡처 대기 중\n창을 영상에 맞추세요", bg="red", fg="white")
                print("\n[-] 연속 캡처 중지")
                
        self.was_key_pressed = is_key_pressed
        
        if self.is_capturing:
            current_time = time.time()
            if current_time - self.last_capture_time >= COOLDOWN:
                self.take_screenshot()
                self.last_capture_time = current_time
                
        self.root.after(50, self.capture_loop)
        
    def take_screenshot(self):
        # 윈도우 내부 클라이언트 영역(빨간 테두리 안쪽 투명한 부분)의 절대 좌표 계산
        x = self.root.winfo_rootx() + 3
        y = self.root.winfo_rooty() + 3
        w = self.root.winfo_width() - 6
        h = self.root.winfo_height() - 6
        
        if w <= 10 or h <= 10: 
            return
            
        monitor = {"top": y, "left": x, "width": w, "height": h}
        
        with mss.mss() as sct:
            # 1. 화면 캡처
            sct_img = sct.grab(monitor)
            img = np.array(sct_img)
            
            # 2. 알파 채널 제거 (BGRA -> BGR)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # 3. 학습 데이터 일관성을 위해 800x600 (4:3) 강제 리사이징
            # 사용자가 창을 어떤 비율로 맞추든 AI 모델이 동일한 해상도를 보도록 평탄화
            img_resized = cv2.resize(img_bgr, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_AREA)
            
            # 4. 파일 저장
            filename = f"yt_frame_{int(time.time() * 1000)}.png"
            filepath = os.path.join(OUTPUT_DIR, filename)
            
            cv2.imwrite(filepath, img_resized)
            print(f"  -> 캡처 및 정규화 완료: {filename} (원본 {w}x{h} -> 변환 {TARGET_WIDTH}x{TARGET_HEIGHT})")

if __name__ == "__main__":
    print("=" * 50)
    print("  [유튜브/스트리밍 화면 전용 캡처 툴]")
    print("  GUI 오버레이 창이 실행되었습니다.")
    print("=" * 50)
    app = CaptureOverlay()
    app.root.mainloop()
