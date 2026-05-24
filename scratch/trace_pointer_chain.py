import sys
import os
import struct
import pymem
import pymem.process

def find_pointer_path(pm, start_addresses, target_addr, max_depth=4):
    """
    start_addresses에서 출발하여 target_addr를 가리키는 포인터 체인을 BFS/DFS로 탐색합니다.
    """
    print(f"[*] Pathfinding from {len(start_addresses)} base pointers to target {hex(target_addr)} (Max Depth: {max_depth})...")
    
    # 큐: (현재 주소, 현재까지의 경로 [(addr, offset, name)])
    # 경로 요소: (parent_addr, offset_from_parent, child_addr)
    queue = []
    for name, addr in start_addresses.items():
        queue.append((addr, 0, [(name, 0, addr)]))
        
    visited = set()
    solutions = []
    
    step = 0
    while queue:
        # Depth별로 끊어서 정보 출력
        step += 1
        next_queue = []
        print(f"    [Depth {step}] Queue size: {len(queue)}")
        
        for curr_addr, depth, path in queue:
            if curr_addr in visited:
                continue
            visited.add(curr_addr)
            
            # target_addr와의 거리 계산
            dist = target_addr - curr_addr
            # 만약 현재 주소 블록의 오프셋 범위 내에 target_addr가 존재한다면!
            # 보통 구조체 크기는 0x4000 이하입니다. 오프셋이 음수일 수도 있으므로 넓게 검색 (-0x1000 ~ 0x4000)
            if -0x1000 <= dist <= 0x4000 and dist % 4 == 0:
                print(f"    [🎉 SUCCESS] Path found at Depth {depth}!")
                solutions.append(path + [("WEIGHT", dist, target_addr)])
                
            if depth >= max_depth:
                continue
                
            # 현재 주소의 메모리 블록을 읽어서 포인터 후보군 색출 (1바이트 정렬 기준으로 정밀 스캔)
            try:
                # 0x3000 바이트 범위 내에서 8바이트 포인터들 모두 스캔
                mem_size = 0x3000
                mem_bytes = pm.read_bytes(curr_addr, mem_size)
                
                extra = len(mem_bytes) % 8
                bytes_to_unpack = mem_bytes[:-extra] if extra else mem_bytes
                
                for i, (val,) in enumerate(struct.iter_unpack("<Q", bytes_to_unpack)):
                    # 유효한 64비트 가상 주소 범위 검사
                    if val != 0 and (val & 0x7fffffffffff) == val and val > 0x10000000:
                        offset = i * 8
                        next_queue.append((val, depth + 1, path + [(hex(offset), offset, val)]))
            except Exception:
                pass
                
        queue = next_queue
        if len(solutions) > 5 or step > max_depth:
            break
            
    return solutions

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 70)
    print("  Deep Cybernetic Pointer Path Solver")
    print("=" * 70)
    
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        
        # 스캔의 시발점이 될 캐릭터 베이스 구조체의 다양한 위치들
        char_base = base + 0x149b350
        
        # 스캔의 기점들: char_base의 주요 포인터 오프셋들 대입
        start_addresses = {}
        
        # char_base 자체
        start_addresses["char_base"] = char_base
        
        # char_base 내부의 포인터들을 기점으로 대입
        try:
            mem_bytes = pm.read_bytes(char_base, 0x300)
            for i in range(0, 0x300, 8):
                val = struct.unpack("<Q", mem_bytes[i:i+8])[0]
                if val != 0 and (val & 0x7fffffffffff) == val and val > 0x10000000:
                    start_addresses[f"char_base+{hex(i)}"] = val
        except Exception as e:
            print(f"[-] Failed to read char_base: {e}")
            return
            
        # target_addr는 이전 스캔에서 찾아낸 실시간 진짜 무게 주소
        # (만약 이전 주소인 0x822ab1c644가 힙 재할당으로 깨졌을 수 있으므로 직접 수동 스캔을 통해 실시간 target_addr 재도출)
        target_w = 25
        print(f"[*] 현재 실시간 무게={target_w}% 값을 가진 주소를 힙에서 다시 탐색 중...")
        
        # 힙 영역 매핑 및 스캔
        from manual_offset_patcher import get_readable_regions, scan_heap_for_value
        regions = get_readable_regions(pm)
        addr_list = scan_heap_for_value(pm, regions, target_w)
        
        approx_food_val = 100 # 포만감 10% -> 100
        golden_addresses = []
        for addr in addr_list:
            try:
                struct_data = pm.read_bytes(addr - 1024, 2048)
                for off in range(0, 2048 - 4, 4):
                    val = int.from_bytes(struct_data[off:off+4], byteorder='little', signed=True)
                    if abs(val - approx_food_val) <= 15:
                        real_dist = off - 1024
                        if abs(real_dist) <= 512:
                            golden_addresses.append((addr, real_dist, val))
                            break
            except Exception:
                pass
                
        if not golden_addresses:
            print("[-] 실시간 무게 절대 주소를 힙에서 도출해내지 못했습니다. 게임 상태를 확인해 주세요.")
            return
            
        target_addr, food_offset_dist, detected_food = golden_addresses[0]
        print(f"[+] 실시간 무게 절대 주소 확정: {hex(target_addr)}")
        
        # 탐색 가동!
        paths = find_pointer_path(pm, start_addresses, target_addr, max_depth=3)
        
        print("\n" + "=" * 70)
        if paths:
            print(f"[🎉 SUCCESS] 총 {len(paths)}개의 유효한 포인터 체인이 발견되었습니다!")
            for idx, path in enumerate(paths):
                print(f"\n[체인 #{idx+1}]:")
                for step_idx, node in enumerate(path):
                    name, offset, addr = node
                    if step_idx == 0:
                        print(f"    기점: {name} ({hex(addr)})")
                    elif step_idx == len(path) - 1:
                        print(f"    ➡️  최종 변수 오프셋: {hex(offset)} (주소: {hex(addr)})")
                    else:
                        print(f"    ➡️  포인터 오프셋: {name} (다음 주소: {hex(addr)})")
                        
            # 첫 번째 체인을 기준으로 자동 패치 실행
            best_path = paths[0]
            # best_path 예시: [("char_base+0xb8", 0xb8, lvl1), ("0xca0", 0xca0, lvl2), ("0xe48", 0xe48, lvl3), ("WEIGHT", 0xe00, target_addr)]
            # 단, 기점이 char_base+0xXX 인 경우와 char_base 자체인 경우에 따라 레벨 처리가 달라집니다.
            
            # 오프셋들을 추출
            off1 = 0
            off2 = 0
            off3 = 0
            wt_off = 0
            
            # 기점이 char_base+0xXX 형태인 경우
            base_node = best_path[0]
            if "+" in base_node[0]:
                off1 = int(base_node[0].split("+")[1], 16)
                
            # 중간 포인터 오프셋들
            ptr_offsets = []
            for node in best_path[1:-1]:
                ptr_offsets.append(node[1])
                
            wt_off = best_path[-1][1]
            fd_off = wt_off + food_offset_dist
            
            # 3레벨 체인이 완성된 경우
            if len(ptr_offsets) == 2:
                off2, off3 = ptr_offsets
                print(f"\n[*] 3레벨 체인 패치 진행:")
                print(f"    lvl1_entry: {hex(off1)}")
                print(f"    lvl1_off: {hex(off2)}")
                print(f"    lvl2_off: {hex(off3)}")
                print(f"    lvl3_wt_off: {hex(wt_off)}")
                print(f"    lvl3_fd_off: {hex(fd_off)}")
                
                from manual_offset_patcher import patch_reader_file
                patch_reader_file(off1, off2, off3, wt_off, fd_off)
                
            # 2레벨 체인이 완성된 경우
            elif len(ptr_offsets) == 1:
                off2 = ptr_offsets[0]
                print(f"\n[*] 2레벨 체인 감지됨! (구조체 레이어가 1단계 축소됨)")
                print(f"    lvl1_entry: {hex(off1)}")
                print(f"    lvl1_off: {hex(off2)}")
                print(f"    lvl2_wt_off: {hex(wt_off)}")
                print(f"    lvl2_fd_off: {hex(fd_off)}")
                
                # 2레벨 체인에 맞춰 mem_state_reader.py 패치 로직 구현
                patch_2level_reader(off1, off2, wt_off, fd_off)
                
        else:
            print("[-] target_addr를 가리키는 유효한 포인터 체인을 찾지 못했습니다.")
        print("=" * 70)
        
    except Exception as e:
        print(f"[-] Error in main: {e}")

def patch_2level_reader(off1, off2, wt_off, fd_off):
    file_path = "mem_state_reader.py"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # weight_chain 치환
        chain_pattern = r"self\.weight_chain\s*=\s*\{[^}]*\}"
        new_chain = f"""self.weight_chain = {{
            "lvl1_off": {hex(off2)},
            "lvl2_off": 0,
            "lvl3_wt_off": {hex(wt_off)},
            "lvl3_fd_off": {hex(fd_off)}
        }}"""
        content = re.sub(chain_pattern, new_chain, content)
        
        # 진입 오프셋 교정
        content = content.replace("char_base + 0xb0", f"char_base + {hex(off1)}")
        content = content.replace("char_base + 0xc0", f"char_base + {hex(off1)}")
        
        # Level 및 EXP Offset 교정
        level_pattern = r"\"level\":\s*0x149b36c"
        content = re.sub(level_pattern, '"level": 0x149b608', content)
        
        exp_pattern = r"\"exp_abs\":\s*0x149b378"
        content = re.sub(exp_pattern, '"exp_abs": 0x149b614', content)
        
        # get_state의 3단계 리딩을 2단계 리딩으로 수정
        # 기존:
        # lvl2 = self.pm.read_longlong(lvl1 + self.weight_chain["lvl1_off"])
        # if lvl2 > 0:
        #     lvl3 = self.pm.read_longlong(lvl2 + self.weight_chain["lvl2_off"])
        #     if lvl3 > 0:
        #         weight = self.pm.read_int(lvl3 + self.weight_chain["lvl3_wt_off"])
        #         food = self.pm.read_int(lvl3 + self.weight_chain["lvl3_fd_off"])
        #
        # 2단계 수정안:
        # lvl2 = self.pm.read_longlong(lvl1 + self.weight_chain["lvl1_off"])
        # if lvl2 > 0:
        #     weight = self.pm.read_int(lvl2 + self.weight_chain["lvl3_wt_off"])
        #     food = self.pm.read_int(lvl2 + self.weight_chain["lvl3_fd_off"])
        
        old_read_block = """                    lvl2 = self.pm.read_longlong(lvl1 + self.weight_chain["lvl1_off"])
                    if lvl2 > 0:
                        lvl3 = self.pm.read_longlong(lvl2 + self.weight_chain["lvl2_off"])
                        if lvl3 > 0:
                            weight = self.pm.read_int(lvl3 + self.weight_chain["lvl3_wt_off"])
                            food = self.pm.read_int(lvl3 + self.weight_chain["lvl3_fd_off"])"""
                            
        new_read_block = """                    lvl2 = self.pm.read_longlong(lvl1 + self.weight_chain["lvl1_off"])
                    if lvl2 > 0:
                        if self.weight_chain["lvl2_off"] > 0:
                            lvl3 = self.pm.read_longlong(lvl2 + self.weight_chain["lvl2_off"])
                            if lvl3 > 0:
                                weight = self.pm.read_int(lvl3 + self.weight_chain["lvl3_wt_off"])
                                food = self.pm.read_int(lvl3 + self.weight_chain["lvl3_fd_off"])
                        else:
                            weight = self.pm.read_int(lvl2 + self.weight_chain["lvl3_wt_off"])
                            food = self.pm.read_int(lvl2 + self.weight_chain["lvl3_fd_off"])"""
                            
        content = content.replace(old_read_block, new_read_block)
        
        # 자가치유 부분 리딩 루틴도 동일하게 수정
        old_heal_block = """                        lvl2 = self.pm.read_longlong(lvl1 + self.weight_chain["lvl1_off"])
                        if lvl2 > 0:
                            lvl3 = self.pm.read_longlong(lvl2 + self.weight_chain["lvl2_off"])
                            if lvl3 > 0:
                                weight = self.pm.read_int(lvl3 + self.weight_chain["lvl3_wt_off"])
                                food = self.pm.read_int(lvl3 + self.weight_chain["lvl3_fd_off"])"""
                                
        new_heal_block = """                        lvl2 = self.pm.read_longlong(lvl1 + self.weight_chain["lvl1_off"])
                        if lvl2 > 0:
                            if self.weight_chain["lvl2_off"] > 0:
                                lvl3 = self.pm.read_longlong(lvl2 + self.weight_chain["lvl2_off"])
                                if lvl3 > 0:
                                    weight = self.pm.read_int(lvl3 + self.weight_chain["lvl3_wt_off"])
                                    food = self.pm.read_int(lvl3 + self.weight_chain["lvl3_fd_off"])
                            else:
                                weight = self.pm.read_int(lvl2 + self.weight_chain["lvl3_wt_off"])
                                food = self.pm.read_int(lvl2 + self.weight_chain["lvl3_fd_off"])"""
                                
        content = content.replace(old_heal_block, new_heal_block)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"[+] {file_path} 2단계 리딩 구조 최적화 패치 성공!")
    except Exception as e:
        print(f"[-] 2단계 패치 실패: {e}")

if __name__ == "__main__":
    main()
