import pymem
import pymem.process
import ctypes
import struct
import time
import sys

def get_heap_matches(pm, process_handle, base, limit):
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
    
    # 임시 수집용: WEIGHT=35, FOOD=66 (실제 현재 캐릭터 스탯 기준)
    target_weight = 35
    target_food = 66
    
    weight_pattern = struct.pack("<i", target_weight)
    matches = []
    
    while kernel32.VirtualQueryEx(process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)) > 0:
        if mbi.State == 0x1000 and mbi.Protect in (0x04, 0x40):
            reg_start = address
            reg_size = mbi.RegionSize
            if not (base <= reg_start < limit):
                try:
                    region_bytes = pm.read_bytes(reg_start, reg_size)
                    offset = 0
                    while True:
                        idx = region_bytes.find(weight_pattern, offset)
                        if idx == -1:
                            break
                        w_addr = reg_start + idx
                        f_addr = w_addr + 8
                        if idx + 12 <= reg_size:
                            f_val = struct.unpack("<i", region_bytes[idx + 8:idx + 12])[0]
                            if f_val == target_food:
                                matches.append((w_addr, f_addr))
                        offset = idx + 4
                except Exception:
                    pass
        address += mbi.RegionSize
    return matches

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        process_handle = pm.process_handle
        
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        limit = base + module.SizeOfImage
        
        print("[*] 1. Initializing Heap Scan to find matches...")
        matches = get_heap_matches(pm, process_handle, base, limit)
        print(f"[+] Initial scan found {len(matches)} potential weight/food heap addresses.")
        
        if not matches:
            print("[-] No matching addresses found. Please make sure character has Weight=35 and Food=62.")
            return
            
        print("\n[*] 2. Starting Dynamic Value Tracker.")
        print("[!] Please perform an action in game that changes WEIGHT or FOOD (e.g. eat food, throw/pickup item, move until food drops).")
        print("[*] Monitoring all candidates in real-time... Press Ctrl+C to stop.")
        print("-" * 80)
        
        # 각 후보에 대해 이전 값을 기록
        prev_vals = {}
        for w_addr, f_addr in matches:
            prev_vals[w_addr] = (35, 62)
            
        sec = 0
        while True:
            changed_candidates = []
            
            for w_addr, f_addr in matches:
                try:
                    curr_w = pm.read_int(w_addr)
                    curr_f = pm.read_int(f_addr)
                    
                    prev_w, prev_f = prev_vals[w_addr]
                    
                    if curr_w != prev_w or curr_f != prev_f:
                        print(f"\n[!!! VALUE CHANGED !!!]")
                        print(f"    Heap Weight Address: {hex(w_addr)}: {prev_w} -> {curr_w}")
                        print(f"    Heap Food Address:   {hex(f_addr)}: {prev_f} -> {curr_f}")
                        prev_vals[w_addr] = (curr_w, curr_f)
                        changed_candidates.append((w_addr, f_addr, curr_w, curr_f))
                except Exception:
                    pass
                    
            sec += 1
            if sec % 5 == 0:
                print(f"[Status] Checked {len(matches)} addresses... (Elapsed: {sec}s)")
                sys.stdout.flush()
                
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\n[*] Tracker stopped by user.")
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
