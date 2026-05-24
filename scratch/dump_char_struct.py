import sys
import struct
import pymem
import pymem.process

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print("  Character Base Memory Structure Dumper")
    print("=" * 60)
    
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        char_base = base + 0x149b350
        print(f"[+] connected to LC.exe (Base: {hex(base)})")
        print(f"[+] Character Base Address: {hex(char_base)}")
        
        size = 0x200
        try:
            mem_bytes = pm.read_bytes(char_base, size)
        except Exception as e:
            print(f"[-] Failed to read memory: {e}")
            return
            
        print("\n[*] Dumping 4-Byte Integer Structure (Offset 0x00 to 0x200)...")
        print("-" * 60)
        print(f"{'Offset':<10} | {'Hex Address':<16} | {'Int32 Value':<15} | {'Float Value':<15}")
        print("-" * 60)
        
        for i in range(0, size, 4):
            val_int = struct.unpack("<i", mem_bytes[i:i+4])[0]
            val_float = struct.unpack("<f", mem_bytes[i:i+4])[0]
            print(f"{hex(i):<10} | {hex(char_base + i):<16} | {val_int:<15} | {val_float:.6f}")
            
        print("=" * 60)
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
