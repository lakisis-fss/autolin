import pymem
import pymem.process
import pydirectinput
import time
import sys
import random

# --- 사용자 제어 설정 ---
TARGET_PROCESS = "LC.exe"
HP_OFFSET = 0x149b35c       # [검증 완료] 실시간 내 캐릭터 HP 주소 오프셋
MAX_HP_OFFSET = 0x149b360   # [검증 완료] 실시간 내 캐릭터 MaxHP 주소 오프셋
HP_THRESHOLD_PCT = 50.0     # 물약을 복용할 체력 백분율 임계치 (50% 미만일 때 작동)
POTION_KEY = 'f1'           # 물약 단축키 설정
COOLDOWN = 1.0              # 물약 연속 복용을 방지하기 위한 쿨타임 (초 단위)
BASE_SCAN_INTERVAL = 0.1    # 기본 상태 스캔 주기 (초 단위)

def run_auto_potion():
    print("[*] Memory-based Stealth Auto Potion System Start")
    print(f"[*] Target Process: {TARGET_PROCESS}")
    print(f"[*] Target Key: {POTION_KEY}")
    print(f"[*] HP Threshold: {HP_THRESHOLD_PCT}%")
    print(f"[*] Cooldown: {COOLDOWN}s")
    print("-" * 60)

    pm = None
    base_address = 0
    hp_address = 0
    max_hp_address = 0
    last_potion_time = 0

    while True:
        # 1. 프로세스 연결 관리 (자가 치유 및 자동 재부착)
        if pm is None:
            try:
                pm = pymem.Pymem(TARGET_PROCESS)
                module = pymem.process.module_from_name(pm.process_handle, TARGET_PROCESS)
                base_address = module.lpBaseOfDll
                hp_address = base_address + HP_OFFSET
                max_hp_address = base_address + MAX_HP_OFFSET
                print(f"\n[+] Connected to {TARGET_PROCESS} Successfully.")
                print(f"    Base Address: {hex(base_address)}")
                print(f"    HP Read Point: {hex(hp_address)}")
                print(f"    MaxHP Read Point: {hex(max_hp_address)}")
                print("[-] Monitoring Live Memory Telemetry...")
            except Exception:
                sys.stdout.write("\r[-] Searching for Lineage Classic process (LC.exe)... Retrying in 5 seconds")
                sys.stdout.flush()
                pm = None
                time.sleep(5.0)
                continue

        # 2. 메모리 리딩 루프
        try:
            current_hp = pm.read_int(hp_address)
            max_hp = pm.read_int(max_hp_address)

            # 유효하지 않은 데이터가 탐지될 경우 무시하고 건너뜀 (메모리 포인터 재배치 등 대응)
            if current_hp < 0 or max_hp <= 0 or current_hp > 100000 or max_hp > 100000:
                time.sleep(1.0)
                continue

            # 체력 백분율 계산
            hp_pct = (current_hp / max_hp) * 100.0

            # 콘솔 창에 실시간으로 상태 기록 (백그라운드에서 실시간 모니터링 시 가시성 확보)
            sys.stdout.write(f"\r[Telemetry] HP: {current_hp}/{max_hp} ({hp_pct:.2f}%)   ")
            sys.stdout.flush()

            # 3. 임계치 비교 및 스텔스 입력 제어
            if hp_pct <= HP_THRESHOLD_PCT:
                current_time = time.time()
                
                # 쿨타임 제어
                if current_time - last_potion_time >= COOLDOWN:
                    print(f"\n[ALERT] HP Low ({hp_pct:.2f}%)! Simulating Stealth Press of Key: {POTION_KEY}")
                    
                    # 안티 치트 우회를 위해 사람이 직접 꾹 눌렀다 떼는 것처럼 키 누름 시간을 불규칙하게 시뮬레이션
                    press_duration = random.uniform(0.05, 0.15)
                    pydirectinput.press(POTION_KEY, duration=press_duration)
                    
                    last_potion_time = current_time
                else:
                    # 쿨타임 대기 중일 때는 연속 입력을 생략하여 마우스/키보드 입력 난사 감지 회피
                    pass

        except Exception as e:
            # 게임이 강제 종료되거나 맵 이동으로 주소 접근 차단 시 안전하게 재연결 프로세스로 회귀
            print(f"\n[-] Memory Read Error: {e}. Attaching pipeline again...")
            pm = None
            time.sleep(2.0)
            continue

        # 4. 안티 치트 행위 분석 우회를 위해 체크 주기에 랜덤성 부여 (Jitter)
        jitter = random.uniform(-0.02, 0.02)
        sleep_time = max(0.01, BASE_SCAN_INTERVAL + jitter)
        time.sleep(sleep_time)

if __name__ == "__main__":
    try:
        run_auto_potion()
    except KeyboardInterrupt:
        print("\n\n[-] Memory-based Auto Potion System Safely Terminated.")
        sys.exit(0)
