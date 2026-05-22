import pymem
import pymem.process
import struct
import sys

def main():
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        char_base = base + 0x149b350
        print(f"[+] Starting Character Base Address: {hex(char_base)} (LC.exe + 0x149b350)")
        
        # 인게임 진짜 스탯
        target_w = 35
        target_f = 66
        
        print(f"[*] 3단계/4단계 깊이 캐릭터 포인터 트리 재귀 탐색 시작... (WEIGHT={target_w}, FOOD={target_f})")
        
        # DFS를 활용하여 포인터 체인을 추적
        found_chains = []
        
        # path: list of (ptr_addr, value, offset_in_parent)
        def search_tree(current_addr, path, depth):
            if depth > 4: # 최대 4단계 깊이까지 조사
                return
                
            # 순환 참조 방지 (현재 경로상에 이미 존재하는 주소인지 확인)
            if any(current_addr == p[0] for p in path):
                return
            
            # 1. 현재 주소에서 WEIGHT=35, FOOD=62가 존재하는지 1차 확인
            try:
                # 힙 구조체 내에서 35와 62가 8바이트 정렬된 상태로 들어있는지 검사
                data_size = 0x1000 # 4KB 크기만 안전하게 읽음
                data_bytes = pm.read_bytes(current_addr, data_size)
                
                for i in range(0, len(data_bytes) - 12, 4):
                    w_val = struct.unpack("<i", data_bytes[i:i+4])[0]
                    f_val = struct.unpack("<i", data_bytes[i+8:i+12])[0]
                    
                    if w_val == target_w and f_val == target_f:
                        # 진짜 찾았다! 포인터 체인 구성 성공!
                        found_chains.append((path, i))
                        print(f"\n[!!! 진짜 캐릭터 포인터 체인 검출 성공 !!!]")
                        print(f"    도달 주소 (Heap Base): {hex(current_addr)}")
                        print(f"    WEIGHT 구조체 오프셋: +{hex(i)}")
                        print(f"    FOOD 구조체 오프셋:   +{hex(i+8)}")
                        
                        # 체인 시각화
                        print("    [체인 경로]")
                        curr_expr = f"[LC.exe + 0x149b350]"
                        for lvl, (ptr, val, off) in enumerate(path):
                            print(f"        Level {lvl+1}: [{hex(ptr)}] -> {hex(val)} (offset: +{hex(off)})")
                            curr_expr = f"[{curr_expr} + {hex(off)}]"
                        print(f"    최종 WEIGHT 공식: {curr_expr} + {hex(i)}")
                        print(f"    최종 FOOD 공식:   {curr_expr} + {hex(i+8)}")
                        
                        # 즉시 파일에 덤프해두어 유실 방증
                        with open("scratch/found_chain.txt", "w") as f:
                            f.write(f"WEIGHT_CHAIN={curr_expr} + {hex(i)}\n")
                            f.write(f"FOOD_CHAIN={curr_expr} + {hex(i+8)}\n")
                            f.write(f"STATIC_OFFSET={hex(path[0][2]) if path else 'N/A'}\n")
                            # 레벨별 오프셋 목록 기록
                            offsets_str = ",".join([hex(x[2]) for x in path])
                            f.write(f"OFFSETS={offsets_str}\n")
                            f.write(f"LAST_OFFSET={hex(i)}\n")
                            
            except Exception:
                pass
                
            # 2. 다음 노드로 가기 위해 현재 주소 내에 존재하는 모든 64비트 포인터(8바이트 정렬) 수집
            try:
                # 구조체에서 다른 힙을 가리키는 포인터가 있을만한 최대 범위 4KB
                page_bytes = pm.read_bytes(current_addr, 0x1000)
                for idx in range(0, len(page_bytes) - 8, 8):
                    val = struct.unpack("<Q", page_bytes[idx:idx+8])[0]
                    # 유효한 64비트 유저 영역 힙 주소인지 필터링 (보통 0x2a000000000 이상)
                    if 0x10000 <= val <= 0x7fffffffffff:
                        # 다음 힙 주소로 재귀 탐색 진행
                        new_path = path + [(current_addr + idx, val, idx)]
                        search_tree(val, new_path, depth + 1)
            except Exception:
                pass
                
        # 캐릭터 구조체 시작점부터 탐색 개시!
        search_tree(char_base, [], 1)
        
        print(f"\n[*] 탐색 완료. 유효 체인 개수: {len(found_chains)}")
        sys.stdout.flush()
        
    except Exception as e:
        print(f"[-] 에러: {e}")

if __name__ == "__main__":
    main()
