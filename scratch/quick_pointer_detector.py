import pymem
import pymem.process
import struct

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        char_base = base + 0x149b350
        lvl1 = pm.read_longlong(char_base + 0x298)
        lvl2 = pm.read_longlong(lvl1 + 0x150)
        
        print(f"[+] Base: {hex(base)}")
        print(f"[+] Lvl1 Ptr: {hex(lvl1)}")
        print(f"[+] Lvl2 Ptr: {hex(lvl2)}")
        
        target_w = 35
        target_f = 66
        
        print(f"[*] Scanning lvl2 structural area (0x0 ~ 0x2000) for paths to real WT={target_w}, FD={target_f}...")
        
        # lvl2 구조체로부터 포인터 수집
        lvl2_bytes = pm.read_bytes(lvl2, 0x2000)
        
        found = 0
        for lvl3_off in range(0, len(lvl2_bytes) - 8, 8):
            lvl3 = struct.unpack("<Q", lvl2_bytes[lvl3_off:lvl3_off+8])[0]
            if 0x10000 <= lvl3 <= 0x7fffffffffff:
                # 이 lvl3가 가리키는 힙 구조체 내를 검사
                try:
                    lvl3_bytes = pm.read_bytes(lvl3, 0x1000)
                    for val_off in range(0, len(lvl3_bytes) - 12, 4):
                        w_val = struct.unpack("<i", lvl3_bytes[val_off:val_off+4])[0]
                        f_val = struct.unpack("<i", lvl3_bytes[val_off+8:val_off+12])[0]
                        if w_val == target_w and f_val == target_f:
                            print(f"\n[!!! FOUND VALID POINTER PATH !!!]")
                            print(f"    Level 3 Offset: {hex(lvl3_off)} (Pointer: {hex(lvl3)})")
                            print(f"    Value Offset:   {hex(val_off)}")
                            print(f"    Formula: [[[[LC.exe + 0x149b350] + 0x298] + 0x150] + {hex(lvl3_off)}] + {hex(val_off)}")
                            found += 1
                except Exception:
                    pass
                    
        print(f"\n[*] Scan completed. Found {found} path(s).")
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
