import pymem
import pymem.process
import struct

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        char_base = base + 0x149b350
        print(f"[+] Character Base Address: {hex(char_base)} (LC.exe + 0x149b350)")
        
        # WEIGHT=35, FOOD=62 (실제 인게임 수치)
        target_w = 35
        target_f = 62
        
        print(f"[*] 캐릭터 메인 구조체 인근 (-0x500 ~ +0x1000) 범위에서 35(WEIGHT)와 62(FOOD) 검색 중...")
        
        # 1바이트 정렬 기준으로 4바이트 정수를 모두 스캔
        # (혹시 2바이트나 1바이트 변수일 수 있으므로 다양한 형식 검사)
        struct_data = pm.read_bytes(char_base - 0x500, 0x1500)
        
        found_candidates = []
        
        # 1. 4바이트 정수 기준 매칭
        for i in range(0, len(struct_data) - 4):
            val_32 = struct.unpack("<i", struct_data[i:i+4])[0]
            val_16 = struct.unpack("<h", struct_data[i:i+2])[0]
            val_8 = struct_data[i]
            
            offset = (char_base - 0x500 + i) - char_base
            
            if val_32 == target_w or val_16 == target_w or val_8 == target_w:
                type_str = "int32" if val_32 == target_w else ("int16" if val_16 == target_w else "int8")
                # 인접한 곳 (+0x0 ~ +0x100 범위)에 FOOD(62)도 발견되는지 함께 스캔
                for j in range(0, len(struct_data) - 4):
                    f_val_32 = struct.unpack("<i", struct_data[j:j+4])[0]
                    f_val_16 = struct.unpack("<h", struct_data[j:j+2])[0]
                    f_val_8 = struct_data[j]
                    
                    f_offset = (char_base - 0x500 + j) - char_base
                    
                    # 두 오프셋의 거리가 가까운 경우 (보통 256바이트 이내)
                    if abs(f_offset - offset) < 256:
                        if f_val_32 == target_f or f_val_16 == target_f or f_val_8 == target_f:
                            f_type_str = "int32" if f_val_32 == target_f else ("int16" if f_val_16 == target_f else "int8")
                            
                            found_candidates.append({
                                "w_offset": offset,
                                "w_type": type_str,
                                "w_val": target_w,
                                "f_offset": f_offset,
                                "f_type": f_type_str,
                                "f_val": target_f,
                                "dist": f_offset - offset
                            })
                            
        print(f"\n[+] 발견된 매칭 후보군 ({len(found_candidates)}개):")
        # 중복 제거 및 정렬해서 출력
        seen = set()
        for cand in found_candidates:
            key = (cand["w_offset"], cand["f_offset"], cand["w_type"], cand["f_type"])
            if key not in seen:
                seen.add(key)
                print(f"    후보:")
                print(f"        WEIGHT: LC.exe + {hex(0x149b350 + cand['w_offset'])} (오프셋: {hex(cand['w_offset'])}, 타입: {cand['w_type']}) = {cand['w_val']}")
                print(f"        FOOD:   LC.exe + {hex(0x149b350 + cand['f_offset'])} (오프셋: {hex(cand['f_offset'])}, 타입: {cand['f_type']}) = {cand['f_val']}")
                print(f"        간격:   {cand['dist']} bytes")
                print("-" * 60)
                
    except Exception as e:
        print(f"[-] 에러: {e}")

if __name__ == "__main__":
    main()
