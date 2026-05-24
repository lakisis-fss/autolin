import os
import sys
import struct
import pymem
import pymem.process
import re

def get_valid_pointers(pm, addr, size=0x2000):
    """지정된 주소의 메모리 블록을 읽어서 유효한 64비트 가상 주소 포인터 목록을 반환합니다."""
    pointers = []
    try:
        data = pm.read_bytes(addr, size)
        extra = len(data) % 8
        bytes_to_unpack = data[:-extra] if extra else data
        for i, (val,) in enumerate(struct.iter_unpack("<Q", bytes_to_unpack)):
            # 64비트 유효 가상 주소 범위 (보통 0x10000000000 ~ 0x7ffffffffff)
            if val != 0 and (val & 0x7fffffffffff) == val and val > 0x10000000:
                pointers.append((i * 8, val))
    except Exception:
        pass
    return pointers

def scan_block_for_stats(pm, addr, target_w, target_f_min, target_f_max, size=0x3000):
    """
    특정 주소 블록 내에 target_w와 target_f가 일치하는 상대 오프셋 조합이 존재하는지 스캔합니다.
    """
    try:
        data = pm.read_bytes(addr, size)
        # 4바이트 정렬 정수 스캔
        for i in range(0, len(data) - 4, 4):
            w_val = struct.unpack("<i", data[i:i+4])[0]
            if w_val == target_w:
                # WEIGHT가 발견된 지점 주변 ±512 바이트 이내에서 FOOD 스캔
                for j in range(max(0, i - 512), min(len(data) - 4, i + 512), 4):
                    if i == j:
                        continue
                    f_val = struct.unpack("<i", data[j:j+4])[0]
                    if target_f_min <= f_val <= target_f_max:
                        return i, j, f_val
    except Exception:
        pass
    return None

def patch_mem_state_reader(levels, wt_off, fd_off):
    file_path = "mem_state_reader.py"
    if not os.path.exists(file_path):
        print(f"[-] {file_path} 파일이 존재하지 않습니다.")
        return False
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        off1, off2, off3 = 0, 0, 0
        if len(levels) == 3: # 3레벨 체인
            off1, off2, off3 = levels
            chain_str = f"""self.weight_chain = {{
            "lvl1_off": {hex(off2)},
            "lvl2_off": {hex(off3)},
            "lvl3_wt_off": {hex(wt_off)},
            "lvl3_fd_off": {hex(fd_off)}
        }}"""
        elif len(levels) == 2: # 2레벨 체인
            off1, off2 = levels
            chain_str = f"""self.weight_chain = {{
            "lvl1_off": {hex(off2)},
            "lvl2_off": 0,
            "lvl3_wt_off": {hex(wt_off)},
            "lvl3_fd_off": {hex(fd_off)}
        }}"""
        else:
            print("[-] 지원하지 않는 체인 깊이입니다.")
            return False
            
        # 1. weight_chain 블록 치환
        chain_pattern = r"self\.weight_chain\s*=\s*\{[^}]*\}"
        content = re.sub(chain_pattern, chain_str, content)
        
        # 2. char_base + 0xXX 진입 오프셋 교정
        content = content.replace("char_base + 0xb0", f"char_base + {hex(off1)}")
        content = content.replace("char_base + 0xc0", f"char_base + {hex(off1)}")
        
        # 3. Level 및 EXP Offset 교정
        # Level: 0x2b8로 변경
        level_pattern = r"\"level\":\s*0x149b36c"
        content = re.sub(level_pattern, '"level": 0x149b608', content)
        
        exp_pattern = r"\"exp_abs\":\s*0x149b378"
        content = re.sub(exp_pattern, '"exp_abs": 0x149b614', content)
        
        # 2단계/3단계 유동 리딩 로직 통합 패치
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
            
        print(f"\n[+] {file_path} 파일 최종 미려한 오프셋 체인 자동 패치 완료!")
        return True
    except Exception as e:
        print(f"[-] 파일 패치 중 오류 발생: {e}")
        return False

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 70)
    print("  리니지 클래식 초고속 100% 무결성 포인터 트리 스캐너")
    print("=" * 70)
    
    target_w = 51
    target_f_min = 900 # 포만감 100% 부근 (900 ~ 1005)
    target_f_max = 1005
    
    try:
        pm = pymem.Pymem("LC.exe")
        module = pymem.process.module_from_name(pm.process_handle, "LC.exe")
        base = module.lpBaseOfDll
        char_base = base + 0x149b350
        print(f"[+] connected to LC.exe (Base: {hex(base)})")
        print(f"[+] Character Base Address: {hex(char_base)}")
    except Exception as e:
        print(f"[-] 게임 연결 실패: {e}")
        return
        
    print(f"[*] 탐색 시작: WEIGHT={target_w}%, FOOD={target_f_min}~{target_f_max}")
    print("[*] 캐릭터 베이스로부터 포인터 트리 탐색 개시...")
    
    # 1단계 포인터 색출 (char_base 내부)
    lvl1_ptrs = get_valid_pointers(pm, char_base, size=0x300)
    print(f"    [+] 1단계 진입 포인터(lvl1): {len(lvl1_ptrs)}개 검출.")
    
    solutions = []
    
    for off1, lvl1 in lvl1_ptrs:
        # --- 2단계 탐색 (lvl1 에서 바로 무게 장부가 존재하는지 검사: 2레벨 체인) ---
        res = scan_block_for_stats(pm, lvl1, target_w, target_f_min, target_f_max)
        if res:
            wt_off, fd_off, fd_val = res
            print(f"\n[🎉 GOLDEN 2-LEVEL CHAIN DETECTED!]")
            print(f"    [Base] + {hex(off1)} -> lvl1 ({hex(lvl1)})")
            print(f"    ➡️  WEIGHT: lvl1 + {hex(wt_off)} ({target_w}%)")
            print(f"    ➡️  FOOD:   lvl1 + {hex(fd_off)} ({fd_val})")
            solutions.append(([off1, wt_off], wt_off, fd_off))
            break
            
        # --- 3단계 탐색 (lvl1 내부의 포인터들을 검사) ---
        lvl2_ptrs = get_valid_pointers(pm, lvl1, size=0x2000)
        for off2, lvl2 in lvl2_ptrs:
            # --- 3단계 탐색 (lvl2 에서 바로 무게 장부가 존재하는지 검사: 3레벨 체인) ---
            res = scan_block_for_stats(pm, lvl2, target_w, target_f_min, target_f_max)
            if res:
                wt_off, fd_off, fd_val = res
                print(f"\n[🎉 GOLDEN 3-LEVEL CHAIN DETECTED!]")
                print(f"    [Base] + {hex(off1)} -> lvl1 ({hex(lvl1)})")
                print(f"    [lvl1] + {hex(off2)} -> lvl2 ({hex(lvl2)})")
                print(f"    ➡️  WEIGHT: lvl2 + {hex(wt_off)} ({target_w}%)")
                print(f"    ➡️  FOOD:   lvl2 + {hex(fd_off)} ({fd_val})")
                solutions.append(([off1, off2, wt_off], wt_off, fd_off))
                break
                
            # --- 4단계 탐색 (lvl2 내부의 포인터들을 검사: 4레벨 체인) ---
            lvl3_ptrs = get_valid_pointers(pm, lvl2, size=0x2000)
            for off3, lvl3 in lvl3_ptrs:
                res = scan_block_for_stats(pm, lvl3, target_w, target_f_min, target_f_max)
                if res:
                    wt_off, fd_off, fd_val = res
                    print(f"\n[🎉 GOLDEN 4-LEVEL CHAIN DETECTED!]")
                    print(f"    [Base] + {hex(off1)} -> lvl1 ({hex(lvl1)})")
                    print(f"    [lvl1] + {hex(off2)} -> lvl2 ({hex(lvl2)})")
                    print(f"    [lvl2] + {hex(off3)} -> lvl3 ({hex(lvl3)})")
                    print(f"    ➡️  WEIGHT: lvl3 + {hex(wt_off)} ({target_w}%)")
                    print(f"    ➡️  FOOD:   lvl3 + {hex(fd_off)} ({fd_val})")
                    solutions.append(([off1, off2, off3, wt_off], wt_off, fd_off))
                    break
            if solutions:
                break
        if solutions:
            break
            
    print("\n" + "=" * 70)
    if solutions:
        best_sol = solutions[0]
        levels, wt_off, fd_off = best_sol
        print(f"[+] 100% 무결성 포인터 체인 추출 완료: {levels}")
        
        # 패치 진행
        if len(levels) <= 3:
            patch_mem_state_reader(levels[:-1], wt_off, fd_off)
        else:
            print("[-] 4레벨 체인은 현재 mem_state_reader.py 구조에서 직접 지원하지 않습니다. 수동 분석 필요.")
    else:
        print("[-] 캐릭터 베이스 포인터 트리 상에서 WEIGHT=25 및 FOOD=100 근처의 조합을 발견하지 못했습니다.")
    print("=" * 70)

if __name__ == "__main__":
    main()
