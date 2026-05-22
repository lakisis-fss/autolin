import pymem
import pymem.process
import struct

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        # HP 오프셋 기준 주소: base + 0x149b35c
        start_addr = base + 0x149b350
        print(f"[+] Base Address: {hex(base)}")
        print(f"[+] Character Struct Dump from {hex(start_addr)}:")
        
        for offset in range(0, 80, 4):
            addr = start_addr + offset
            val = pm.read_int(addr)
            print(f"    Offset +{offset} ({hex(0x149b350 + offset)}): {val} (hex: {hex(val)})")
            
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
