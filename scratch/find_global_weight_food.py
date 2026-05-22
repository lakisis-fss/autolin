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
        
        target_weight = 35
        target_food = 62
        
        print(f"[*] Scanning ENTIRE virtual memory space of LC.exe for WEIGHT={target_weight} and FOOD={target_food}...")
        
        kernel32 = ctypes.windll.kernel32
        class MEMORY_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BaseAddress", ctypes.c_void_p),
                ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_ulong),
                ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.c_ulong),
                ("Protect", ctypes.c_ulong),
                ("Type", ctypes.c_ulong),
            ]
            
        mbi = MEMORY_BASIC_INFORMATION()
        address = 0
        
        weight_pattern = struct.pack("<i", target_weight)
        food_pattern = struct.pack("<i", target_food)
        
        valid_hits = []
        max_distance = 256  # WEIGHT와 FOOD가 스탯 구조체 내부에 있다면 보통 256바이트 이내에 존재함.
        
        # 0x000000000000 ~ 0x7fffffffffff 가상 메모리 공간 전수조사
        while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            # MEM_COMMIT = 0x1000, Protect: PAGE_READWRITE = 0x04, PAGE_EXECUTE_READWRITE = 0x40
            if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40):
                reg_start = address
                reg_size = mbi.RegionSize
                
                try:
                    region_bytes = pm.read_bytes(reg_start, reg_size)
                    
                    # 1. 먼저 WEIGHT(35) 주소들을 수집
                    offset = 0
                    w_offsets = []
                    while True:
                        idx = region_bytes.find(weight_pattern, offset)
                        if idx == -1:
                            break
                        w_offsets.append(idx)
                        offset = idx + 4
                        
                    # 2. 각 WEIGHT 주소 주변에 FOOD(62)가 존재하는지 1차 필터링
                    for w_idx in w_offsets:
                        w_addr = reg_start + w_idx
                        
                        # w_idx 기준 주변 메모리 서칭
                        search_start_idx = max(0, w_idx - max_distance)
                        search_end_idx = min(reg_size, w_idx + max_distance)
                        
                        context_bytes = region_bytes[search_start_idx:search_end_idx]
                        
                        # context_bytes 안에서 FOOD(62) 패턴 찾기
                        food_offset = 0
                        while True:
                            f_idx = context_bytes.find(food_pattern, food_offset)
                            if f_idx == -1:
                                break
                            
                            f_addr = reg_start + search_start_idx + f_idx
                            dist = f_addr - w_addr
                            
                            is_static = base <= w_addr < limit
                            region_type = "STATIC" if is_static else ("HEAP" if mbi.Type == 0x20000 else "PRIVATE")
                            
                            valid_hits.append((w_addr, f_addr, dist, region_type))
                            food_offset = f_idx + 4
                            
                except Exception:
                    pass
                    
            address += mbi.RegionSize
            
        print(f"\n[+] Global Scan Results (Found {len(valid_hits)} matches):")
        # 100개까지만 상세 덤프
        for w, f, d, r_type in valid_hits[:100]:
            print(f"    Match Pair ({r_type}):")
            print(f"        WEIGHT Addr: {hex(w)} (offset from base: {hex(w - base) if r_type == 'STATIC' else 'N/A'})")
            print(f"        FOOD Addr:   {hex(f)} (offset from base: {hex(f - base) if r_type == 'STATIC' else 'N/A'})")
            print(f"        Distance:    {d} bytes")
            
            # 인근 정수 덤프
            try:
                dump_start = min(w, f) - 16
                dump_end = max(w, f) + 16
                dump_size = dump_end - dump_start
                print("        Nearby Integers:")
                for off in range(0, dump_size + 4, 4):
                    addr = dump_start + off
                    val = pm.read_int(addr)
                    mark = " <- WEIGHT" if addr == w else (" <- FOOD" if addr == f else "")
                    print(f"            Address {hex(addr)}: {val}{mark}")
            except Exception as e:
                print(f"            Dump error: {e}")
            print("-" * 60)
            
    except Exception as e:
        print(f"[-] Global scan error: {e}")

if __name__ == "__main__":
    main()
