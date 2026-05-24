import sys
import struct
import pymem
import pymem.process
import ctypes

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        char_base = base + 0x149b350  # We will use the static fallback for testing
        print(f"[+] connected to LC.exe (Base: {hex(base)})")
        print(f"[+] Character Base Address: {hex(char_base)}")
        
        # Targets
        target_wt = 30
        target_fd = 170
        target_exp_pct = 60.9572
        
        print("\n--- 1. SCANNING FOR EXP ---")
        # Scan char_base for exp
        try:
            char_data = pm.read_bytes(char_base, 0x1000)
            for i in range(0, len(char_data) - 4, 4):
                val = struct.unpack("<i", char_data[i:i+4])[0]
                if 4000000 <= val <= 4500000:
                    ratio = target_exp_pct / val if val != 0 else 0
                    print(f"  [EXP CANDIDATE] Offset: {hex(i)} | Value: {val} | Calculated Ratio: {ratio:.8e}")
        except Exception as e:
            print(f"Error reading char_base: {e}")
            
        print("\n--- 2. SCANNING FOR WT AND FD IN HEAP TREES ---")
        static_ptrs = []
        for off in range(0, 0x300, 8):
            try:
                val = pm.read_longlong(char_base + off)
                if val != 0 and (val & 0x7fffffffffff) == val and val > 0x10000000:
                    static_ptrs.append((off, val))
            except:
                pass
                
        found_chain = False
        for off1, lvl1 in static_ptrs:
            try:
                lvl1_bytes = pm.read_bytes(lvl1, 0x2000)
                extra1 = len(lvl1_bytes) % 8
                bytes_to_unpack1 = lvl1_bytes[:-extra1] if extra1 else lvl1_bytes
                
                for i2, (lvl2,) in enumerate(struct.iter_unpack("<Q", bytes_to_unpack1)):
                    if lvl2 != 0 and (lvl2 & 0x7fffffffffff) == lvl2 and lvl2 > 0x10000000:
                        off2 = i2 * 8
                        try:
                            lvl2_bytes = pm.read_bytes(lvl2, 0x2000)
                            
                            # 3레벨 체인 스캔 (lvl2 장부)
                            for w_off in range(0, len(lvl2_bytes) - 4, 4):
                                w_val = struct.unpack("<i", lvl2_bytes[w_off:w_off+4])[0]
                                if w_val == target_wt:
                                    for f_off in range(max(0, w_off - 32), min(len(lvl2_bytes) - 4, w_off + 32), 4):
                                        f_val = struct.unpack("<i", lvl2_bytes[f_off:f_off+4])[0]
                                        if f_val == target_fd or f_val == target_fd + 1 or f_val == target_fd - 1:
                                            print(f"  [FOUND WT/FD - 2 Level Deep]")
                                            print(f"    lvl1_entry: {hex(off1)}")
                                            print(f"    lvl1_off: {hex(off2)}")
                                            print(f"    wt_off: {hex(w_off)} | fd_off: {hex(f_off)}")
                                            found_chain = True
                            
                            extra2 = len(lvl2_bytes) % 8
                            bytes_to_unpack2 = lvl2_bytes[:-extra2] if extra2 else lvl2_bytes
                            
                            for i3, (lvl3,) in enumerate(struct.iter_unpack("<Q", bytes_to_unpack2)):
                                if lvl3 != 0 and (lvl3 & 0x7fffffffffff) == lvl3 and lvl3 > 0x10000000:
                                    off3 = i3 * 8
                                    try:
                                        lvl3_bytes = pm.read_bytes(lvl3, 0x2000)
                                        for w_off in range(0, len(lvl3_bytes) - 4, 4):
                                            w_val = struct.unpack("<i", lvl3_bytes[w_off:w_off+4])[0]
                                            if w_val == target_wt:
                                                for f_off in range(max(0, w_off - 32), min(len(lvl3_bytes) - 4, w_off + 32), 4):
                                                    f_val = struct.unpack("<i", lvl3_bytes[f_off:f_off+4])[0]
                                                    if f_val == target_fd or f_val == target_fd + 1 or f_val == target_fd - 1:
                                                        print(f"  [FOUND WT/FD - 3 Level Deep]")
                                                        print(f"    lvl1_entry: {hex(off1)}")
                                                        print(f"    lvl1_off: {hex(off2)}")
                                                        print(f"    lvl2_off: {hex(off3)}")
                                                        print(f"    wt_off: {hex(w_off)} | fd_off: {hex(f_off)}")
                                                        found_chain = True
                                    except:
                                        pass
                        except:
                            pass
            except:
                pass
                
        if not found_chain:
            print("  [-] Could not find WT=30 and FD=170 chain.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
