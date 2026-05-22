import pymem
import pymem.process
import struct

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        char_base = base + 0x149b350
        print(f"[+] Character Base Address: {hex(char_base)} (LC.exe + 0x149b350)")
        
        # 1. 0x149b350 주변의 포인터 후보군들 덤프 및 검사
        # 캐릭터 구조체의 크기는 대략 수백 바이트에서 수 KB일 수 있으므로 -0x1000 ~ +0x1000 범위 조사
        scan_start = char_base - 0x1000
        scan_end = char_base + 0x2000
        
        print(f"[*] Scanning pointer candidates from {hex(scan_start)} to {hex(scan_end)}...")
        
        # 8바이트 정렬된 주소들을 돌며 64비트 포인터 값을 읽어옴
        for addr in range(scan_start, scan_end, 8):
            try:
                ptr_val = pm.read_longlong(addr)
                
                # 64비트 유효한 사용자 공간 주소인지 대략적인 필터링 (Windows 64비트 기준 0x000000000000 ~ 0x7fffffffffff)
                if 0x10000 <= ptr_val <= 0x7fffffffffff:
                    # 이 포인터가 가리키는 힙 공간에서 WEIGHT=35, FOOD=62 가 8바이트 간격으로 존재하는지 검사
                    # 힙 구조체의 크기도 수 KB일 수 있으므로 0 ~ 0x4000 범위 스캔
                    try:
                        heap_bytes = pm.read_bytes(ptr_val, 0x4000)
                        
                        # WEIGHT=35, FOOD=62 가 8바이트 간격으로 붙어있는지 확인
                        # 즉, heap_bytes[i:i+4] == 35 이고 heap_bytes[i+8:i+12] == 62 인 i 찾기
                        for i in range(0, len(heap_bytes) - 12, 4):
                            w_val = struct.unpack("<i", heap_bytes[i:i+4])[0]
                            f_val = struct.unpack("<i", heap_bytes[i+8:i+12])[0]
                            
                            if w_val == 35 and f_val == 62:
                                static_offset = addr - base
                                print(f"\n[!!! FOUND EXACT MATCH !!!]")
                                print(f"    Static Address: LC.exe + {hex(static_offset)} ({hex(addr)})")
                                print(f"    Points to Heap Address: {hex(ptr_val)}")
                                print(f"    Structure Weight Offset: +{hex(i)} (val: {w_val})")
                                print(f"    Structure Food Offset:   +{hex(i+8)} (val: {f_val})")
                                print(f"    Pointer chain to WEIGHT: [LC.exe + {hex(static_offset)}] + {hex(i)}")
                                print(f"    Pointer chain to FOOD:   [LC.exe + {hex(static_offset)}] + {hex(i+8)}")
                    except Exception:
                        pass
            except Exception:
                pass
                
        print("\n[*] Scan finished.")
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
