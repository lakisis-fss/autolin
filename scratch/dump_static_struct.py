import pymem
import pymem.process
import struct

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        start_offset = 0x149b350
        print(f"[+] Static module base: {hex(base)}")
        print(f"[*] Dumping 4-byte integers starting from LC.exe + {hex(start_offset)}...")
        
        for offset in range(0, 0x100, 4):
            addr = base + start_offset + offset
            val = pm.read_int(addr)
            # 8바이트 float 이나 double 도 존재할 수 있으므로 해석 출력
            try:
                val_double = struct.unpack("<d", pm.read_bytes(addr, 8))[0]
            except Exception:
                val_double = 0.0
                
            try:
                val_float = struct.unpack("<f", pm.read_bytes(addr, 4))[0]
            except Exception:
                val_float = 0.0
                
            label = ""
            if offset == 0: label = "X"
            elif offset == 4: label = "Y"
            elif offset == 8: label = "Heading"
            elif offset == 0xc: label = "HP"
            elif offset == 0x10: label = "MaxHP"
            elif offset == 0x14: label = "MP"
            elif offset == 0x16 or offset == 0x18: label = "MaxMP"
            elif offset == 0x1c: label = "Level"
            elif offset == 0x28: label = "ExpAbs"
            
            print(f"    Offset +{hex(offset)} ({hex(start_offset + offset)}): Int={val} | Float={val_float:.4f} | Double={val_double:.4f}  {label}")
            
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
