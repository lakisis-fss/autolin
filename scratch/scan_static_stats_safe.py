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
        target_food_min = 62
        target_food_max = 62
        
        print(f"[*] Scanning committed static regions of LC.exe for WEIGHT={target_weight} and FOOD={target_food_min}~{target_food_max}...")
        
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
        
        weight_addresses = []
        weight_pattern = struct.pack("<i", target_weight)
        
        while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            # MEM_COMMIT = 0x1000, Protect: PAGE_READWRITE = 0x04, PAGE_EXECUTE_READWRITE = 0x40
            if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40):
                # 정적 모듈 범위와 겹치는지 체크
                reg_start = address
                reg_end = address + mbi.RegionSize
                
                # 정적 데이터 세그먼트 영역에 완전히 또는 일부 속하는 경우만 캡처!
                if reg_start < limit and reg_end > base:
                    try:
                        region_bytes = pm.read_bytes(reg_start, mbi.RegionSize)
                        offset = 0
                        while True:
                            idx = region_bytes.find(weight_pattern, offset)
                            if idx == -1:
                                break
                            w_addr = reg_start + idx
                            # 정확하게 정적 모듈 범위 내인지 검사
                            if base <= w_addr < limit:
                                weight_addresses.append(w_addr)
                            offset = idx + 4
                    except Exception:
                        pass
            address += mbi.RegionSize
            
        print(f"[+] Found {len(weight_addresses)} weight (35) candidates in static committed segment.")
        
        # 2. 각 WEIGHT 주소 인근에 포만감이 있는지 필터링
        valid_hits = []
        for w_addr in weight_addresses:
            try:
                search_start = w_addr - 128
                context_bytes = pm.read_bytes(search_start, 256)
                
                for offset in range(0, len(context_bytes) - 4, 4):
                    val = int.from_bytes(context_bytes[offset:offset+4], byteorder='little', signed=True)
                    if target_food_min <= val <= target_food_max:
                        food_addr = search_start + offset
                        dist = food_addr - w_addr
                        valid_hits.append((w_addr, food_addr, dist, val))
            except Exception:
                pass
                
        print(f"\n[+] Static Segment Candidates (Found {len(valid_hits)} matches):")
        for w, f, d, f_val in valid_hits:
            w_off = w - base
            f_off = f - base
            print(f"    Candidate Match:")
            print(f"        WEIGHT Addr: {hex(w)} (LC.exe + {hex(w_off)})")
            print(f"        FOOD Addr:   {hex(f)} (LC.exe + {hex(f_off)}) | Value: {f_val}")
            print(f"        Distance:    {d} bytes")
            
            # 인근 메모리 정수 덤프
            try:
                dump_start = w - 32
                print("        Nearby Integers:")
                for off in range(0, 64, 4):
                    addr = dump_start + off
                    v = pm.read_int(addr)
                    mark = " <- WEIGHT" if addr == w else (" <- FOOD" if addr == f else "")
                    print(f"            LC.exe + {hex(addr - base)}: {v}{mark}")
            except Exception:
                pass
            print("-" * 60)
            
    except Exception as e:
        print(f"[-] Safe Scan error: {e}")

if __name__ == "__main__":
    main()
