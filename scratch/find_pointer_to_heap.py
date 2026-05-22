import pymem
import pymem.process
import ctypes
import struct

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        process_handle = pm.process_handle
        
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        size = module.SizeOfImage
        limit = base + size
        print(f"[+] Static module range: {hex(base)} ~ {hex(limit)}")
        
        # 이전 전역 스캔에서 찾은 WEIGHT 힙 주소: 0x2a408c70621
        # 이 주변의 구조체 시작점이 될 수 있는 다양한 8바이트 정렬 주소들을 타겟팅!
        target_heap_addresses = [
            0x2a408c70620,  # 8바이트 정렬된 WEIGHT 주소 자체
            0x2a408c70600,  # 0x20 바이트 앞 (구조체 시작점 후보)
            0x2a408c70610,  # 0x10 바이트 앞
            0x2a408c70628,  # FOOD 주소 정렬
            0x2a408c705e0,  # 덤프에서 이상한 큰 값(-16777216 등)이 시작되던 곳 근처
        ]
        
        print(f"[*] Searching for pointers pointing to heap structures near 0x2a408c70620 in static module...")
        
        # 1. 정적 모듈 바이트 전체 리딩
        module_bytes = pm.read_bytes(base, size)
        
        # 2. 각 타겟 힙 주소에 대해 8바이트 포인터 패턴 스캔
        found_pointers = []
        for t_addr in target_heap_addresses:
            pointer_pattern = struct.pack("<Q", t_addr) # 64비트 포인터 리틀엔디언
            
            offset = 0
            while True:
                idx = module_bytes.find(pointer_pattern, offset)
                if idx == -1:
                    break
                p_addr = base + idx
                found_pointers.append((t_addr, p_addr))
                offset = idx + 8
                
        print(f"\n[+] Static Pointer Scan Results (Found {len(found_pointers)} static pointers):")
        for t, p in found_pointers:
            print(f"    Heap Target: {hex(t)} <- Pointed by Static Addr: {hex(p)} (LC.exe + {hex(p - base)})")
            
        # 만약 직접적인 1단계 포인터가 없으면, 조금 범위(Range)를 주어서 
        # "힙 주소의 앞부분(Base)을 가리키는 포인터"를 찾기 위해 힙 주소 상위 40비트만 일치하는 포인터를 검색해본다.
        if not found_pointers:
            print("\n[*] No exact pointer found. Scanning for pointers to the same 64KB heap page (0x2a408c70000 ~ 0x2a408c80000)...")
            heap_page_start = 0x2a408c70000
            heap_page_end = 0x2a408c80000
            
            # 정적 모듈 바이트에서 8바이트씩 꺼내서 64비트 주소로 해석한 뒤, 이 범위에 들어오는지 전수조사!
            page_pointers = []
            for idx in range(0, size - 8, 8):
                val = struct.unpack("<Q", module_bytes[idx:idx+8])[0]
                if heap_page_start <= val < heap_page_end:
                    p_addr = base + idx
                    page_pointers.append((val, p_addr))
                    
            print(f"[+] Found {len(page_pointers)} pointers to the same heap page in static module:")
            for val, p in page_pointers[:50]:
                offset_in_heap = val - heap_page_start
                print(f"    Points to Heap Address: {hex(val)} (offset from page start: {hex(offset_in_heap)})")
                print(f"    Static Pointer Address: {hex(p)} (LC.exe + {hex(p - base)})")
                print("-" * 50)
                
    except Exception as e:
        print(f"[-] Pointer search error: {e}")

if __name__ == "__main__":
    main()
