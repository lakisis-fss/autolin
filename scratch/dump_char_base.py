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
        print(f"Base: {hex(base)}")
        print(f"char_base: {hex(char_base)}")
        
        print("\n=== Dumping Static char_base Region (4-byte integers) ===")
        # 100% 검증된 스탯들 먼저 표시
        pos_x = pm.read_int(char_base + 0)
        pos_y = pm.read_int(char_base + 4)
        heading = pm.read_int(char_base + 8)
        hp = pm.read_int(char_base + 12)
        max_hp = pm.read_int(char_base + 16)
        mp = pm.read_int(char_base + 20)
        max_mp = pm.read_int(char_base + 24)
        level = pm.read_int(char_base + 28)
        exp = pm.read_int(char_base + 40)
        
        print(f"[VERIFIED] pos_x (+0x0): {pos_x}")
        print(f"[VERIFIED] pos_y (+0x4): {pos_y}")
        print(f"[VERIFIED] heading (+0x8): {heading}")
        print(f"[VERIFIED] hp (+0xc): {hp}")
        print(f"[VERIFIED] max_hp (+0x10): {max_hp}")
        print(f"[VERIFIED] mp (+0x14): {mp}")
        print(f"[VERIFIED] max_mp (+0x18): {max_mp}")
        print(f"[VERIFIED] level (+0x1c): {level}")
        print(f"[VERIFIED] exp (+0x28): {exp}")
        
        print("\n--- Scanning other offsets for Weight=35 or Food=731 ---")
        for offset in range(0, 0x300, 4):
            try:
                val = pm.read_int(char_base + offset)
                val_short = pm.read_short(char_base + offset)
                val_float = pm.read_float(char_base + offset)
                
                # 무게 35나 포만감 731 근처의 값을 찾음
                if val == 35 or (700 <= val <= 750):
                    print(f"Offset {hex(offset)} (int): {val}")
                if 70.0 <= val_float <= 75.0 or 34.0 <= val_float <= 36.0:
                    print(f"Offset {hex(offset)} (float): {val_float:.3f}")
            except Exception:
                pass
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
