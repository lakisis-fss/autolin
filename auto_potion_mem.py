import pymem
import pymem.process
import pydirectinput
import time
import sys

# --- 사용자 설정 ---
TARGET_PROCESS = "LC.exe"
HP_OFFSET = 0x143603c  # 검증된 내 캐릭터 HP 오프셋
HP_THRESHOLD = 80      # 이 수치보다 HP가 낮아지면 물약을 먹습니다 (수동 변경 가능)
POTION_KEY = 'f1'      # 물약 스킬/아이템이 등록된 단축키
SCAN_INTERVAL = 0.1    # 체크 간격 (초)

def run_auto_potion():
    try:
        # LC.exe 연결
        pm = pymem.Pymem(TARGET_PROCESS)
        module = pymem.process.module_from_name(pm.process_handle, TARGET_PROCESS)
        base_address = module.lpBaseOfDll
        hp_address = base_address + HP_OFFSET
        
        print(f"[*] Memory-based Auto Potion Started.")
        print(f"[*] 모니터링 주소: {hex(hp_address)}")
        print(f"[*] 설정 임계치: HP {HP_THRESHOLD} 미만 시 [{POTION_KEY}] 입력")
        print("-" * 50)
        
        while True:
            try:
                # 메모리에서 현재 HP 읽기
                current_hp = pm.read_int(hp_address)
                
                # 가끔 메모리 읽기 오류가 날 수 있으므로 체크
                if current_hp < 0 or current_hp > 50000: # 비정상적인 수치
                    time.sleep(1)
                    continue

                sys.stdout.write(f"\r[실시간 HP] {current_hp}   ")
                sys.stdout.flush()

                # 조건 확인
                if current_hp < HP_THRESHOLD:
                    print(f"\n[!] HP 위험: {current_hp} -> [{POTION_KEY}] 키 입력!")
                    pydirectinput.press(POTION_KEY)
                    # 물약 쿨타임을 고려하여 약간 대기
                    time.sleep(0.5) 
                
                time.sleep(SCAN_INTERVAL)
                
            except Exception as e:
                print(f"\n[-] 루프 내 오류: {e}")
                time.sleep(1)
                
    except Exception as e:
        print(f"[-] LC.exe 연결 실패: {e}")

if __name__ == "__main__":
    print("--- Memory-based Auto Potion System ---")
    try:
        run_auto_potion()
    except KeyboardInterrupt:
        print("\n\n시스템을 종료합니다.")
