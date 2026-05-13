import pymem
import pymem.process

def find_offsets(target_addresses):
    try:
        # LC.exe 프로세스에 연결
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base_address = module.lpBaseOfDll
        
        print(f"[*] LC.exe Base Address: {hex(base_address)}")
        print("-" * 50)
        
        for addr in target_addresses:
            offset = addr - base_address
            # 현재 메모리 값 다시 읽기 (검증용)
            try:
                current_val = pm.read_int(addr)
                print(f"대상 주소: {hex(addr)}")
                print(f"계산된 오프셋 (Base + Offset): LC.exe + {hex(offset)}")
                print(f"현재 메모리 값: {current_val}")
                print("-" * 50)
            except Exception as e:
                print(f"[-] 주소 {hex(addr)} 읽기 실패: {e}")
            
    except Exception as e:
        print(f"[-] LC.exe 연결 실패: {e}")

if __name__ == "__main__":
    # 스캐너에서 찾은 최종 주소 2개를 여기에 입력하세요
    # 예: [0x1fd92a16688, 0x7ff7639a603c]
    target_list = [0x1fd92a16688, 0x7ff7639a603c]
    
    print("--- Offset Finder for LC.exe ---")
    find_offsets(target_list)
