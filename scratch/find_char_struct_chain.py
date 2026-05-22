import pymem
import pymem.process
import struct

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        # dynamic_stat_tracker에서 감지한 진짜 WEIGHT 주소
        target_w_addr = 0x2a455667a80
        target_f_addr = 0x2a455667a88
        
        print(f"[+] Target 스탯 주소: WEIGHT={hex(target_w_addr)}, FOOD={hex(target_f_addr)}")
        
        # 1. 캐릭터 메인 구조체(LC.exe + 0x149b350) 내의 64비트 포인터 리스트 수집
        char_base = base + 0x149b350
        print(f"[*] 캐릭터 메인 구조체(LC.exe + 0x149b350)에서 힙 포인터 수집 중...")
        
        heap_pointers = []
        for off in range(0, 0x400, 8): # 조금 더 넉넉하게 1KB 범위 수집
            ptr_addr = char_base + off
            try:
                val = pm.read_longlong(ptr_addr)
                # 유효한 64비트 유저 주소 영역 필터링
                if 0x10000 <= val <= 0x7fffffffffff:
                    heap_pointers.append((off, ptr_addr, val))
            except Exception:
                pass
                
        print(f"[+] 수집된 힙 포인터 개수: {len(heap_pointers)}")
        
        # 2. 각 수집된 힙 주소 H 내부를 스캔하여 target_w_addr 주변의 주소를 가리키는 포인터가 있는지 조사
        print(f"[*] 힙 포인터들이 가리키는 메모리 스캔 시작...")
        
        found_chains = 0
        for off, ptr_addr, heap_ptr in heap_pointers:
            try:
                # 힙 객체 크기를 최대 64KB(0x10000)로 상정하고 Readable한 범위만큼 읽어옴
                # 안전하게 16KB(0x4000) 크기만 먼저 조사
                heap_data = pm.read_bytes(heap_ptr, 0x4000)
                
                # 8바이트 정렬된 64비트 값을 꺼내서 검사
                for h_off in range(0, len(heap_data) - 8, 8):
                    val = struct.unpack("<Q", heap_data[h_off:h_off+8])[0]
                    
                    # 이 val이 target_w_addr 주변(즉, target_w_addr를 포함하는 구조체의 시작 주소)인지 검사
                    # 구조체 오프셋이 최대 0x1000(4KB)라고 가정하고 [target_w_addr - 0x1000, target_w_addr] 범위인지 확인
                    if target_w_addr - 0x1000 <= val <= target_w_addr:
                        struct_base = val
                        weight_offset_in_struct = target_w_addr - struct_base
                        food_offset_in_struct = target_f_addr - struct_base
                        
                        static_offset = ptr_addr - base
                        print(f"\n[!!! 2단계 포인터 체인 검출 성공 !!!]")
                        print(f"    1단계 정적 주소: LC.exe + {hex(static_offset)}")
                        print(f"    1단계 가리키는 주소 (Heap 1): {hex(heap_ptr)}")
                        print(f"    Heap 1 내 오프셋: +{hex(h_off)}")
                        print(f"    2단계 가리키는 주소 (Heap 2 base): {hex(struct_base)}")
                        print(f"    WEIGHT 구조체 오프셋: +{hex(weight_offset_in_struct)}")
                        print(f"    FOOD 구조체 오프셋:   +{hex(food_offset_in_struct)}")
                        print(f"\n    [체인식]")
                        print(f"    WEIGHT 주소 = [[LC.exe + {hex(static_offset)}] + {hex(h_off)}] + {hex(weight_offset_in_struct)}")
                        print(f"    FOOD 주소   = [[LC.exe + {hex(static_offset)}] + {hex(h_off)}] + {hex(food_offset_in_struct)}")
                        found_chains += 1
            except Exception:
                pass
                
        print(f"\n[*] 스캔 종료. 총 {found_chains}개의 유효 체인을 발견했습니다.")
        
    except Exception as e:
        print(f"[-] 에러 발생: {e}")

if __name__ == "__main__":
    main()
