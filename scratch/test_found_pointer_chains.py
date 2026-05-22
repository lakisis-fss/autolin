import pymem
import pymem.process
import struct

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        char_base = base + 0x149b350
        print(f"[+] Character Base: {hex(char_base)}")
        
        # 레벨 1 포인터 읽기 (오프셋 0x298)
        lvl1_ptr = pm.read_longlong(char_base + 0x298)
        print(f"[+] Level 1 Ptr: {hex(lvl1_ptr)}")
        
        # 레벨 2 포인터 읽기 (오프셋 0x150)
        lvl2_ptr = pm.read_longlong(lvl1_ptr + 0x150)
        print(f"[+] Level 2 Ptr: {hex(lvl2_ptr)}")
        
        # 레벨 3 오프셋들 후보군 테스트
        # 0x7e0, 0x818, 0x820, 0x858, 0xa18, 0xa20, 0xa58, 0xa60
        lvl3_offsets = [0x7e0, 0x818, 0x820, 0x858, 0xa18, 0xa20, 0xa58, 0xa60]
        
        # 내부에 들어있는 오프셋 후보들: 0x420, 0x450, 0x630, 0x660
        val_offsets = [0x420, 0x450, 0x630, 0x660]
        
        for l3_off in lvl3_offsets:
            try:
                lvl3_ptr = pm.read_longlong(lvl2_ptr + l3_off)
                if 0x10000 <= lvl3_ptr <= 0x7fffffffffff:
                    print(f"\n[*] testing Level 3 Ptr at offset {hex(l3_off)}: {hex(lvl3_ptr)}")
                    for val_off in val_offsets:
                        try:
                            w_val = pm.read_int(lvl3_ptr + val_off)
                            f_val = pm.read_int(lvl3_ptr + val_off + 8)
                            print(f"    Offset {hex(val_off)} -> WEIGHT: {w_val}, FOOD: {f_val}")
                        except Exception:
                            pass
            except Exception as e:
                print(f"    Error reading offset {hex(l3_off)}: {e}")
                
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
