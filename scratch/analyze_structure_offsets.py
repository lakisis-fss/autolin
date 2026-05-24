import sys
import os
import struct
import pymem
import pymem.process

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 70)
    print("  Character Structure Bulk Memory Analyzer")
    print("=" * 70)
    
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        char_base = base + 0x149b350
        print(f"[+] Connected to LC.exe (Base: {hex(base)})")
        print(f"[+] Character Base: {hex(char_base)}")
        
        size = 0x300
        mem_bytes = pm.read_bytes(char_base, size)
        
        print("\n" + "-" * 70)
        print(f"{'Offset':<8} | {'Hex Address':<16} | {'Int32':<12} | {'UInt64 (PointerCandidate)':<18} | {'Hex Int32':<10}")
        print("-" * 70)
        
        for i in range(0, size, 4):
            val_32 = struct.unpack("<i", mem_bytes[i:i+4])[0]
            val_64 = 0
            if i + 8 <= size:
                val_64 = struct.unpack("<Q", mem_bytes[i:i+8])[0]
                
            addr = char_base + i
            ptr_note = ""
            if 0x10000000000 < val_64 < 0x7ffffffffff:
                ptr_note = f"-> {hex(val_64)}"
                
            print(f"{hex(i):<8} | {hex(addr):<16} | {val_32:<12} | {val_64:<18} {ptr_note:<25} | {hex(val_32 & 0xffffffff)}")
            
        print("=" * 70)
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
