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
        
        print(f"[*] Scanning LC.exe committed regions for WEIGHT={target_weight} and FOOD={target_food}...")
        
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
        food_addresses = []
        
        weight_pattern = struct.pack("<i", target_weight)
        food_pattern = struct.pack("<i", target_food)
        
        # 1. 스캔 단계: 전체 Committed & Readable & Writeable 정적 메모리 수집
        while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40):
                reg_start = address
                reg_end = address + mbi.RegionSize
                
                if reg_start < limit and reg_end > base:
                    try:
                        region_bytes = pm.read_bytes(reg_start, mbi.RegionSize)
                        
                        # WEIGHT (35) 수집
                        offset = 0
                        while True:
                            idx = region_bytes.find(weight_pattern, offset)
                            if idx == -1:
                                break
                            w_addr = reg_start + idx
                            if base <= w_addr < limit:
                                weight_addresses.append(w_addr)
                            offset = idx + 4
                            
                        # FOOD (62) 수집
                        offset = 0
                        while True:
                            idx = region_bytes.find(food_pattern, offset)
                            if idx == -1:
                                break
                            f_addr = reg_start + idx
                            if base <= f_addr < limit:
                                food_addresses.append(f_addr)
                            offset = idx + 4
                            
                    except Exception:
                        pass
            address += mbi.RegionSize
            
        print(f"[+] Found {len(weight_addresses)} WEIGHT candidates and {len(food_addresses)} FOOD candidates in static module.")
        
        # 2. 넉넉한 거리(예: 1024바이트) 범위로 상호 교차 매칭 수행
        matches = []
        max_distance = 1024
        
        for w_addr in weight_addresses:
            for f_addr in food_addresses:
                dist = f_addr - w_addr
                if abs(dist) <= max_distance:
                    matches.append((w_addr, f_addr, dist))
                    
        print(f"\n[+] Candidates in static module (Distance <= {max_distance} bytes, Found {len(matches)} matches):")
        for w, f, d in matches:
            w_off = w - base
            f_off = f - base
            print(f"    Candidate Pair:")
            print(f"        WEIGHT Addr: {hex(w)} (LC.exe + {hex(w_off)})")
            print(f"        FOOD Addr:   {hex(f)} (LC.exe + {hex(f_off)})")
            print(f"        Distance:    {d} bytes")
            
            # 인근 정수 덤프
            try:
                dump_start = min(w, f) - 16
                dump_end = max(w, f) + 16
                dump_size = dump_end - dump_start
                print("        Memory Dump (Int32):")
                for off in range(0, dump_size + 4, 4):
                    addr = dump_start + off
                    val = pm.read_int(addr)
                    mark = " <- WEIGHT" if addr == w else (" <- FOOD" if addr == f else "")
                    print(f"            LC.exe + {hex(addr - base)}: {val}{mark}")
            except Exception as e:
                print(f"            Dump Error: {e}")
            print("-" * 60)
            
    except Exception as e:
        print(f"[-] Scan error: {e}")

if __name__ == "__main__":
    main()
