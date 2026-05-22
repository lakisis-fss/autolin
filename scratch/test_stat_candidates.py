import pymem
import pymem.process
import struct
import time

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        char_base = base + 0x149b350
        
        print("="*60)
        print("  Stat Candidates Real-Time Monitor")
        print("="*60)
        
        for idx in range(10):
            print(f"\n[Iteration {idx+1}]")
            
            # 후보 A: 0xb0 -> 0xd30 -> 0xc68 -> 0xe00 / 0xe08
            try:
                lvl1_a = pm.read_longlong(char_base + 0xb0)
                lvl2_a = pm.read_longlong(lvl1_a + 0xd30)
                lvl3_a = pm.read_longlong(lvl2_a + 0xc68)
                w_a = pm.read_int(lvl3_a + 0xe00)
                f_a = pm.read_int(lvl3_a + 0xe08)
                print(f"Candidate A (0xb0->0xd30->0xc68->0xe00): WEIGHT={w_a}, FOOD={f_a}")
            except Exception as e:
                print(f"Candidate A Error: {e}")
                
            # 후보 B: 0xb8 -> 0xca0 -> 0xe40 -> 0xe00 / 0xe08
            try:
                lvl1_b = pm.read_longlong(char_base + 0xb8)
                lvl2_b = pm.read_longlong(lvl1_b + 0xca0)
                lvl3_b = pm.read_longlong(lvl2_b + 0xe40)
                w_b = pm.read_int(lvl3_b + 0xe00)
                f_b = pm.read_int(lvl3_b + 0xe08)
                print(f"Candidate B (0xb8->0xca0->0xe40->0xe00): WEIGHT={w_b}, FOOD={f_b}")
            except Exception as e:
                print(f"Candidate B Error: {e}")
                
            # 기존 후보 (0x298 -> 0x150 -> 0xa60 -> 0x660)
            try:
                lvl1_old = pm.read_longlong(char_base + 0x298)
                lvl2_old = pm.read_longlong(lvl1_old + 0x150)
                lvl3_old = pm.read_longlong(lvl2_old + 0xa60)
                w_old = pm.read_int(lvl3_old + 0x660)
                f_old = pm.read_int(lvl3_old + 0x668)
                print(f"Candidate Old (0x298->0x150->0xa60->0x660): WEIGHT={w_old}, FOOD={f_old}")
            except Exception as e:
                print(f"Candidate Old Error: {e}")
                
            time.sleep(1.0)
            
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
