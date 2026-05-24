import sys
import struct
import pymem
import pymem.process

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 80)
    print("  Fast Character-Base Linear Experience Scanner (Target: 4,418,143)")
    print("=" * 80)
    
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        char_base = base + 0x149b350
        print(f"[+] connected to LC.exe (Base: {hex(base)})")
        print(f"[+] Character Base Address: {hex(char_base)}")
        
        # 65.3849% 일 때 기대하는 실제 경험치 정수량은 대략 4,412,501 ~ 4,420,000 사이
        target_min = 4410000
        target_max = 4425000
        
        # 가상 메모리 스캔 대신, 캐릭터 구조체로부터 뻗어나가는 1차 힙 영역(lvl1)들을 수집하여 
        # 그 내부 데이터를 다이렉트 고속 전수 스캔합니다.
        static_ptrs = []
        for off in range(0, 0x1000, 8):
            try:
                val = pm.read_longlong(char_base + off)
                if val != 0 and (val & 0x7fffffffffff) == val and val > 0x10000000:
                    static_ptrs.append((off, val))
            except:
                pass
                
        print(f"[+] Found {len(static_ptrs)} dynamic pointers near character base.")
        print("-" * 80)
        
        found = False
        for off1, lvl1 in static_ptrs:
            # lvl1 힙 영역 리딩 (0x4000 크기로 넉넉하게 스캔)
            try:
                lvl1_data = pm.read_bytes(lvl1, 0x4000)
                
                # Int32 스캔
                for i in range(0, len(lvl1_data) - 4, 4):
                    val = struct.unpack("<i", lvl1_data[i:i+4])[0]
                    if target_min <= val <= target_max:
                        ratio = 65.3849 / val
                        print(f"[FOUND 1-Level] Base + {hex(off1)} -> lvl1 + {hex(i)} | Value: {val} | Ratio: {ratio:.8e}")
                        found = True
                        
                # 8바이트 언팩하여 lvl2 포인터 추적
                extra = len(lvl1_data) % 8
                bytes_to_unpack = lvl1_data[:-extra] if extra else lvl1_data
                for i2, (lvl2,) in enumerate(struct.iter_unpack("<Q", bytes_to_unpack)):
                    if lvl2 != 0 and (lvl2 & 0x7fffffffffff) == lvl2 and lvl2 > 0x10000000:
                        off2 = i2 * 8
                        try:
                            lvl2_data = pm.read_bytes(lvl2, 0x4000)
                            for i3 in range(0, len(lvl2_data) - 4, 4):
                                val = struct.unpack("<i", lvl2_data[i3:i3+4])[0]
                                if target_min <= val <= target_max:
                                    ratio = 65.3849 / val
                                    print(f"[FOUND 2-Level] Base + {hex(off1)} -> lvl1 + {hex(off2)} -> lvl2 + {hex(i3)} | Value: {val} | Ratio: {ratio:.8e}")
                                    found = True
                        except:
                            pass
            except:
                pass
                
        if not found:
            print("[-] No experience candidates matched in character dynamic heaps.")
            
        print("=" * 80)
        
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
