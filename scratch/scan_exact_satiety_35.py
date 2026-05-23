import sys
sys.stdout.reconfigure(encoding='utf-8')
import pymem
import pymem.process

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        char_base = base + 0x149b350
        lvl1 = pm.read_longlong(char_base + 0xb0)
        print(f"Base: {hex(base)}")
        print(f"char_base: {hex(char_base)}")
        print(f"lvl1: {hex(lvl1)}")
        
        target_w = 35
        # 현재 포만감이 약 73% (730 내외)이므로 여유있게 600~850 사이 탐색
        f_min = 600
        f_max = 850
        
        print(f"\n[*] Scanning lvl1 pointer chain for Weight={target_w} and Food Satiety={f_min}~{f_max}...")
        
        pointers_lvl1 = []
        for offset in range(0, 0x1a00, 8):
            try:
                val = pm.read_longlong(lvl1 + offset)
                if 0x10000000000 < val < 0x7ffffffffff:
                    pointers_lvl1.append((offset, val))
            except Exception:
                pass
                
        print(f"Found {len(pointers_lvl1)} sub-pointers at lvl1.")
        
        found = False
        for off1, lvl2 in pointers_lvl1:
            pointers_lvl2 = []
            for offset2 in range(0, 0x1800, 8):
                try:
                    val2 = pm.read_longlong(lvl2 + offset2)
                    if 0x10000000000 < val2 < 0x7ffffffffff:
                        pointers_lvl2.append((offset2, val2))
                except Exception:
                    pass
            
            for off2, lvl3 in pointers_lvl2:
                for off3 in range(0, 0x3500, 4):
                    try:
                        w_val = pm.read_int(lvl3 + off3)
                        if w_val == target_w:
                            # 무게 35 발견, 주변 ±512바이트에서 food 값 탐색
                            for near_off in range(off3 - 512, off3 + 512, 4):
                                if near_off < 0 or near_off >= 0x3500 or near_off == off3:
                                    continue
                                try:
                                    f_val = pm.read_int(lvl3 + near_off)
                                    if f_min <= f_val <= f_max:
                                        print(f"[FOUND SUCCESS CHAIN!]")
                                        print(f"  lvl1 + {hex(off1)} -> lvl2 + {hex(off2)} -> lvl3 + {hex(off3)} (Weight: {w_val} | Food Offset {hex(near_off)}: {f_val})")
                                        found = True
                                except Exception:
                                    pass
                    except Exception:
                        pass
                        
        if not found:
            print("[-] No matching dynamic chain found for Weight=35 and Food Satiety=600~850.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
