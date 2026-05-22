import pymem
import pymem.process

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        # HP 오프셋 기준 주소: base + 0x149b35c
        start_addr = base + 0x149b350
        print(f"[+] Scanning character struct range (Offset +0 ~ +512) for WEIGHT (35) or FOOD (62)...")
        
        found_hits = []
        for offset in range(0, 512, 4):
            addr = start_addr + offset
            val = pm.read_int(addr)
            # 1바이트 또는 2바이트 단위로도 들어있을 수 있으므로 short/char 형태도 고려
            val_short1 = pm.read_short(addr)
            val_short2 = pm.read_short(addr + 2)
            
            # 덤프 출력
            print(f"    Offset +{offset} ({hex(0x149b350 + offset)}): INT={val} | SHORT1={val_short1}, SHORT2={val_short2}")
            
            # 혹시 무게(35)나 포만감(62)과 정확히 매칭되는 정수가 있는지 체크
            if 35 in (val, val_short1, val_short2):
                found_hits.append((offset, "WEIGHT? (35)"))
            if 62 in (val, val_short1, val_short2):
                found_hits.append((offset, "FOOD? (62)"))
                
        print("\n[+] Matches found in close struct range:")
        for off, name in found_hits:
            print(f"    -> Offset +{off} ({hex(0x149b350 + off)}): {name}")
            
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()
