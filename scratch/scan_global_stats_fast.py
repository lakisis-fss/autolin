import pymem
import pymem.process
import ctypes
import struct

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        process_handle = pm.process_handle
        
        target_weight = 35
        target_food_min = 55
        target_food_max = 65  # 여유 범위를 소폭 더 넓힘 (62 내외)
        
        print(f"[*] Starting Ultra-Fast memory scan for WEIGHT={target_weight} and FOOD={target_food_min}~{target_food_max}...")
        
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
        
        # 1단계: 35 값 초고속 획득
        while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
            if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40):
                try:
                    region_bytes = pm.read_bytes(address, mbi.RegionSize)
                    offset = 0
                    while True:
                        idx = region_bytes.find(weight_pattern, offset)
                        if idx == -1:
                            break
                        weight_addresses.append(address + idx)
                        offset = idx + 4
                except Exception:
                    pass
            address += mbi.RegionSize
            
        print(f"[+] Ultra-Fast Scan completed. Found {len(weight_addresses)} weight addresses containing {target_weight}.")
        
        # 2단계: 주변에 FOOD가 있는지 4바이트 정밀 스캔
        print("[*] Proximity analysis for FOOD (62)...")
        valid_pairs = []
        for w_addr in weight_addresses:
            try:
                # 35 근방 -64 ~ +64바이트 범위 읽기
                search_start = w_addr - 64
                context_bytes = pm.read_bytes(search_start, 128)
                
                # context 영역에서 4바이트 정수들 역추적
                for offset in range(0, len(context_bytes) - 4, 4):
                    val = int.from_bytes(context_bytes[offset:offset+4], byteorder='little', signed=True)
                    if target_food_min <= val <= target_food_max:
                        food_addr = search_start + offset
                        dist = food_addr - w_addr
                        valid_pairs.append((w_addr, food_addr, dist, val))
            except Exception:
                pass
                
        print(f"\n[+] Proximity Filter Results (Found {len(valid_pairs)} candidates):")
        try:
            module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
            base = module.lpBaseOfDll
        except Exception:
            base = 0
            
        for w, f, d, f_val in valid_pairs:
            w_off = w - base if base else 0
            f_off = f - base if base else 0
            
            try:
                nearby_bytes = pm.read_bytes(w - 64, 128)
                has_hp = False
                has_lvl = False
                for i in range(0, len(nearby_bytes) - 4, 4):
                    v = int.from_bytes(nearby_bytes[i:i+4], byteorder='little')
                    if v == 114: has_hp = True
                    if v == 14: has_lvl = True
                    
                tags = []
                if has_hp: tags.append("HP_NEARBY(114)")
                if has_lvl: tags.append("LVL_NEARBY(14)")
                tag_str = ", ".join(tags) if tags else "None"
                
                print(f"    Candidate Match:")
                print(f"        WEIGHT Addr: {hex(w)} (LC.exe + {hex(w_off)})")
                print(f"        FOOD Addr:   {hex(f)} (LC.exe + {hex(f_off)}) | Value: {f_val}")
                print(f"        Distance:    {d} bytes")
                print(f"        Tags:        [{tag_str}]")
            except Exception:
                pass
                
    except Exception as e:
        print(f"[-] Fast Scan error: {e}")

if __name__ == "__main__":
    main()
