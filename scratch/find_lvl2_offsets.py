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
        
        lvl2_710 = pm.read_longlong(lvl1 + 0x710)
        # 현재 활성화된 진짜 lvl3 주소
        target_lvl3 = 0x2744368b660
        
        print(f"Base: {hex(base)}")
        print(f"lvl1: {hex(lvl1)}")
        print(f"lvl2_710: {hex(lvl2_710)}")
        print(f"Searching for target_lvl3 pointer: {hex(target_lvl3)} inside lvl2...")
        
        found_offsets = []
        for offset in range(0, 0x3000, 8):
            try:
                val = pm.read_longlong(lvl2_710 + offset)
                if val == target_lvl3:
                    found_offsets.append(offset)
                    print(f"[FOUND] Offset {hex(offset)} contains target_lvl3 pointer!")
            except Exception:
                pass
                
        if not found_offsets:
            print("[-] No offsets found in lvl2 containing target_lvl3 pointer.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
