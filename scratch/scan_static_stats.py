import pymem
import pymem.process
import struct

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        size = module.SizeOfImage
        print(f"[+] Static module range: {hex(base)} ~ {hex(base + size)}")
        
        target_weight = 35
        target_food_min = 55
        target_food_max = 65
        
        # 1. 정적 모듈 전체 메모리 카피
        mem = pm.read_bytes(base, size)
        print(f"[+] Static memory copied: {len(mem)} bytes")
        
        # 2. bytes.find로 target_weight (35) 탐색
        weight_offsets = []
        weight_pattern = struct.pack("<i", target_weight)
        
        offset = 0
        while True:
            idx = mem.find(weight_pattern, offset)
            if idx == -1:
                break
            weight_offsets.append(idx)
            offset = idx + 4
            
        print(f"[+] Found {len(weight_offsets)} weight (35) candidates inside static module.")
        
        # 3. 각 WEIGHT 오프셋 인근 (+-128바이트) 영역에 FOOD가 있는지 분석
        valid_hits = []
        for w_off in weight_offsets:
            w_addr = base + w_off
            
            # 인근 바이트 덤프
            search_start = max(0, w_off - 128)
            search_end = min(size, w_off + 128)
            context_bytes = mem[search_start:search_end]
            
            for i in range(0, len(context_bytes) - 4, 4):
                val = int.from_bytes(context_bytes[i:i+4], byteorder='little', signed=True)
                if target_food_min <= val <= target_food_max:
                    f_off = search_start + i
                    f_addr = base + f_off
                    dist = f_off - w_off
                    valid_hits.append((w_off, f_off, dist, val))
                    
        print(f"\n[+] Static Segment Candidates (Found {len(valid_hits)} matches):")
        for w_off, f_off, dist, f_val in valid_hits:
            print(f"    Candidate Match:")
            print(f"        WEIGHT Addr: {hex(base + w_off)} (LC.exe + {hex(w_off)})")
            print(f"        FOOD Addr:   {hex(base + f_off)} (LC.exe + {hex(f_off)}) | Value: {f_val}")
            print(f"        Distance:    {dist} bytes")
            
            # 그 주변(+-32바이트) 정수 값들을 쭉 덤프해서 문맥 파악
            try:
                dump_start = max(0, w_off - 32)
                print("        Nearby Integers Dump:")
                for off in range(dump_start, min(size, w_off + 32), 4):
                    v = int.from_bytes(mem[off:off+4], byteorder='little', signed=True)
                    mark = " <- WEIGHT" if off == w_off else (" <- FOOD" if off == f_off else "")
                    print(f"            LC.exe + {hex(off)}: {v}{mark}")
            except Exception:
                pass
            print("-" * 60)
            
    except Exception as e:
        print(f"[-] Static Scan error: {e}")

if __name__ == "__main__":
    main()
