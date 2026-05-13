import pymem
import pymem.process
import time
import sys

def verify_hp():
    try:
        # LC.exe 프로세스에 연결
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base_address = module.lpBaseOfDll
        
        # 앞서 찾은 정적 오프셋
        hp_offset = 0x143603c
        hp_address = base_address + hp_offset
        
        print(f"[*] 게임 베이스 주소: {hex(base_address)}")
        print(f"[*] HP 실시간 주소: {hex(hp_address)}")
        print("-" * 50)
        print("실시간 HP 모니터링을 시작합니다... (Ctrl+C 종료)")
        
        while True:
            try:
                # 4바이트 정수로 HP 읽기
                current_hp = pm.read_int(hp_address)
                # 한 줄에 출력 (업데이트 효과)
                sys.stdout.write(f"\r[실시간 HP] 내 캐릭터: {current_hp}   ")
                sys.stdout.flush()
                time.sleep(0.1) # 100ms 간격
            except Exception as e:
                print(f"\n[-] 메모리 읽기 실패: {e}")
                break
                
    except Exception as e:
        print(f"[-] LC.exe 연결 실패: {e}. 게임이 실행 중인지 확인하세요.")

if __name__ == "__main__":
    print("--- Memory-based HP Monitor for Lineage Classic ---")
    try:
        verify_hp()
    except KeyboardInterrupt:
        print("\n\n모니터링을 종료합니다.")
