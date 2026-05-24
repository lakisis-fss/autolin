import pymem
import pymem.process
import pymem.pattern
import time
import struct
import re
import ctypes

class MemStateReader:
    def __init__(self, process_name="LC.exe"):
        self.process_name = process_name
        self.pm = None
        self.base_address = 0
        
        # AOB 스캐닝 하이브리드 엔진 변수
        # 나중에 치트엔진으로 확실한 패턴을 찾으셨다면 이 곳에 b"\x48\x8B\x05....\x48\x8B\x88" 형태로 붙여넣으세요.
        # 패턴이 비어있거나 스캔에 실패하면 fallback_offset을 자동으로 사용합니다.
        self.char_base_pattern = b"" 
        self.fallback_offset = 0x149b350
        self.dynamic_char_offset = self.fallback_offset
        
        # 동적 캐릭터 프로필 데이터베이스
        # 캐릭터 구조체 변환 감지용 오프셋 정보
        self.profiles = {
            14: {
                "level_off": 0x1c,      # LEVEL 오프셋
                "exp_off": 0x28,        # EXP_Abs 오프셋
                "lvl1_entry": 0xb0,
                "lvl1_off": 0x28
            },
            11: {
                "level_off": 0x2b8,     # LEVEL 오프셋
                "exp_off": 0x2c4,       # EXP_Abs 오프셋
                "lvl1_entry": 0xb0,
                "lvl1_off": 0x28
            }
        }
        
        self.current_profile_lvl = 14
        self.last_attach_attempt = 0
        
        # 하이브리드 경험치 캘리브레이션 정보 (사용 중단, 정적 테이블 사용)
        self.exp_max_table = {
            14: 7238687, # 레벨 14의 100% 도달 필요 경험치 (역산치)
            11: 1800000  # 레벨 11 예시
        }
        
        # 가방 구조체 AOB 지문 (사용자가 create_aob_helper.py 로 추출하여 여기에 붙여넣음)
        self.struct_aob_pattern = b"\x1f\x00\x00\x00\xb0\xac\x00\x00\x16\x00\x0c\x00\x00\x00\x00\x00"
        
        # 포만도 구조체 전용 AOB 지문 (무게와 완전히 다른 힙에 존재함)
        self.struct_fd_aob_pattern = b"\x00\x00\x0c\x42\x00\x00\x84\x42\x00\x00\x00\x00\x10\xa3\x8e\xd0"
        
        # 실시간 가방 무게 및 포만도 정독용 오프셋 캐시 (성능 최적화용)
        self.cached_offsets = {
            "lvl2_off": 0,
            "lvl3_wt_off": 0,
            "lvl3_fd_off": 0
        }
        self.cached_abs_wt_addr = 0
        self.cached_abs_fd_addr = 0
        
        self.exp_cached_offsets = {
            "lvl1_off": 0,
            "lvl2_off": 0
        }

    def attach(self):
        if time.time() - self.last_attach_attempt < 5:
            return False
        self.last_attach_attempt = time.time()
        
        try:
            self.pm = pymem.Pymem(self.process_name)
            module = pymem.process.module_from_name(self.pm.process_handle, self.process_name)
            self.base_address = module.lpBaseOfDll
            
            # 프로세스 연결 직후 AOB 스캐닝 엔진 가동 (1회성)
            self.find_dynamic_base_offset(module)
            
            return True
        except Exception:
            return False

    def find_dynamic_base_offset(self, module):
        """AOB 스캐닝을 통해 게임 모듈(.text)에서 캐릭터 베이스 오프셋을 동적으로 추출합니다."""
        if not self.pm or not module:
            self.dynamic_char_offset = self.fallback_offset
            return

        # 1. 사용자가 AOB 패턴을 입력하지 않았다면 스캔을 건너뛰고 기존 오프셋 사용 (안전 모드)
        if not self.char_base_pattern:
            self.dynamic_char_offset = self.fallback_offset
            return

        try:
            print("[MemStateReader] AOB 스캐닝 가동 중...")
            found_addr = pymem.pattern.pattern_scan_module(self.pm.process_handle, module, self.char_base_pattern)
            
            if found_addr:
                # 64비트 RIP-relative 주소 계산 로직 (명령어 길이 7바이트, 변위 시작점 3바이트 가정)
                # 실제 찾으신 어셈블리 패턴 명령어 구조에 맞게 이 부분을 미세 조정해야 할 수 있습니다.
                displacement = self.pm.read_int(found_addr + 3)
                absolute_address = found_addr + 7 + displacement
                new_offset = absolute_address - module.lpBaseOfDll
                self.dynamic_char_offset = new_offset
                print(f"[MemStateReader] AOB 스캔 성공! 동적 오프셋 획득: 0x{new_offset:x}")
            else:
                print("[MemStateReader] AOB 스캔 실패: 패턴을 찾을 수 없습니다. 안전 모드로 가동합니다.")
                self.dynamic_char_offset = self.fallback_offset
        except Exception as e:
            print(f"[MemStateReader] AOB 스캔 에러 ({e}). 안전 모드로 가동합니다.")
            self.dynamic_char_offset = self.fallback_offset

    def detect_character_profile(self):
        """캐릭터 구조체 정보를 실시간 판독하여 레벨 14 프로필인지 레벨 11 프로필인지 동적 선별"""
        if not self.pm:
            return
            
        try:
            char_base = self.base_address + self.dynamic_char_offset
            
            # 1. 레벨 14 오프셋(0x1c) 검사 (현재 사용자 캐릭터인 레벨 14 최우선 판독)
            val_14 = self.pm.read_int(char_base + 0x1c)
            if val_14 == 14:
                if self.current_profile_lvl != 14:
                    self.current_profile_lvl = 14
                    # 프로필 전환 시 기존 캐시 강제 무효화하여 새로운 세션 캐시 수립 유도
                    self.cached_offsets = {"lvl2_off": 0, "lvl3_wt_off": 0, "lvl3_fd_off": 0}
                    print(f"[MemStateReader] Profile auto-switched to Level 14 based on 0x1c detection.")
                return
                
            # 2. 레벨 11 오프셋(0x2b8) 검사 (레벨 14가 확실히 아닐 때만 레벨 11로 안전 전환)
            val_11 = self.pm.read_int(char_base + 0x2b8)
            if val_11 == 11:
                if self.current_profile_lvl != 11:
                    self.current_profile_lvl = 11
                    self.cached_offsets = {"lvl2_off": 0, "lvl3_wt_off": 0, "lvl3_fd_off": 0}
                    print(f"[MemStateReader] Profile auto-switched to Level 11 based on 0x2b8 detection.")
                return
        except Exception:
            pass

    def update_exp_calibration(self, ocr_exp_str, current_level):
        """[DEPRECATED] 정적 Max EXP 테이블을 사용하므로 더 이상 외부(OCR) 캘리브레이션에 의존하지 않습니다."""
        pass

    def read_stealth_weight_food_via_tree_parser(self):
        """
        초고속 실시간 AOB 힙 스캐너 (Global Heap AOB Scanner)
        이제 복잡한 포인터 체인을 타지 않고, 힙 영역을 단 한 번 전수조사하여
        진짜 무게의 절대 주소를 영구 캐싱합니다.
        """
        if not self.pm:
            return 0, 0
            
        if not self.struct_aob_pattern or len(self.struct_aob_pattern) < 8:
            return 0, 0

        # --- 1. 초고속 캐시 읽기 (1000 FPS) ---
        if self.cached_abs_wt_addr > 0:
            try:
                weight = self.pm.read_int(self.cached_abs_wt_addr)
                food = 0.0
                if self.cached_abs_fd_addr > 0:
                    try:
                        food = self.pm.read_float(self.cached_abs_fd_addr)
                    except:
                        pass
                
                # 유효성 검증 (무게가 0~100 사이인가?)
                if 0 <= weight <= 100:
                    return weight, food
                else:
                    # 무효화되면 캐시 삭제
                    self.cached_abs_wt_addr = 0
                    self.cached_abs_fd_addr = 0
            except Exception:
                self.cached_abs_wt_addr = 0
                self.cached_abs_fd_addr = 0

        # --- 2. 전역 힙 AOB 스캐닝 (초기 1회만 발생, 약 0.5초 소요) ---
        print("[MemStateReader] ⚠️ 구조체 오프셋 이탈 감지! 전역 메모리 힙 AOB 스캐닝 돌입 (최초 1회만 발생)...")
        
        MEM_COMMIT = 0x1000
        PAGE_READWRITE = 0x04
        PAGE_EXECUTE_READWRITE = 0x40
        mbi = ctypes.windll.kernel32.VirtualQueryEx
        
        MB_STRUCT = type('MB_STRUCT', (ctypes.Structure,), {
            '_fields_': [
                ('BaseAddress', ctypes.c_void_p),
                ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', ctypes.c_ulong),
                ('RegionSize', ctypes.c_size_t),
                ('State', ctypes.c_ulong),
                ('Protect', ctypes.c_ulong),
                ('Type', ctypes.c_ulong)
            ]
        })
        mbi_struct = MB_STRUCT()
        
        addr = 0
        wt_fixed_pattern = self.struct_aob_pattern[4:] if self.struct_aob_pattern and len(self.struct_aob_pattern) >= 8 else None
        fd_fixed_pattern = self.struct_fd_aob_pattern[4:] if self.struct_fd_aob_pattern and len(self.struct_fd_aob_pattern) >= 8 else None
        
        while ctypes.windll.kernel32.VirtualQueryEx(self.pm.process_handle, ctypes.c_void_p(addr), ctypes.byref(mbi_struct), ctypes.sizeof(mbi_struct)) > 0:
            if mbi_struct.State == MEM_COMMIT and mbi_struct.Protect in (PAGE_READWRITE, PAGE_EXECUTE_READWRITE):
                try:
                    data = self.pm.read_bytes(addr, mbi_struct.RegionSize)
                    
                    # 무게 AOB 스캔
                    if self.cached_abs_wt_addr == 0 and wt_fixed_pattern:
                        idx_wt = data.find(wt_fixed_pattern)
                        if idx_wt != -1:
                            abs_wt_addr = addr + idx_wt - 4
                            w_val = self.pm.read_int(abs_wt_addr)
                            if 0 <= w_val <= 100:
                                self.cached_abs_wt_addr = abs_wt_addr
                                print(f"[MemStateReader] ✅ AOB 무게 주소 포착: {hex(abs_wt_addr)}")

                    # 포만도 AOB 스캔 (독립적)
                    if self.cached_abs_fd_addr == 0 and fd_fixed_pattern:
                        idx_fd = data.find(fd_fixed_pattern)
                        if idx_fd != -1:
                            abs_fd_addr = addr + idx_fd - 4
                            try:
                                f_val = self.pm.read_float(abs_fd_addr)
                                if 0.0 <= f_val <= 120.0:
                                    self.cached_abs_fd_addr = abs_fd_addr
                                    print(f"[MemStateReader] ✅ AOB 포만도 주소 포착: {hex(abs_fd_addr)}")
                            except Exception:
                                pass
                                
                    # 둘 다 찾았거나, 찾을 수 있는 패턴을 다 찾은 경우 조기 종료
                    if (not wt_fixed_pattern or self.cached_abs_wt_addr != 0) and (not fd_fixed_pattern or self.cached_abs_fd_addr != 0):
                        break
                        
                except Exception:
                    pass
            addr += mbi_struct.RegionSize
            
        weight = self.pm.read_int(self.cached_abs_wt_addr) if self.cached_abs_wt_addr > 0 else 0
        try:
            food = self.pm.read_float(self.cached_abs_fd_addr) if self.cached_abs_fd_addr > 0 else 0.0
        except:
            food = 0.0
        return weight, food

    def read_stealth_exp_via_tree_parser(self, target_exp=None):
        """
        [DEPRECATED] 정적 오프셋 롤백으로 더 이상 사용되지 않습니다.
        """
        return 0

    def get_state(self):
        if not self.pm:
            if not self.attach():
                return None

        try:
            # 0. 매 프레임마다 현재 캐릭터 프로필 자동 선별
            self.detect_character_profile()
            
            profile = self.profiles.get(self.current_profile_lvl)
            if not profile:
                return None
                
            char_base = self.base_address + self.dynamic_char_offset
            
            # 1. 체력, 마나, 레벨, 절대경험치 획득
            hp = self.pm.read_int(char_base + 0xc)
            max_hp = self.pm.read_int(char_base + 0x10)
            mp = self.pm.read_int(char_base + 0x14)
            max_mp = self.pm.read_int(char_base + 0x18)
            level = self.pm.read_int(char_base + profile["level_off"])
            
            # 절대 경험치를 정적으로 직접 정독 (상호 참조 힌트 없이 순수 메모리 정독)
            exp_abs = self.pm.read_int(char_base + profile["exp_off"])
            
            # 2. 초고속 실시간 트리 해석 파서를 통해 가방 무게/포만감 정독 (힌트 없이 스스로 동적 역추적)
            weight, food = self.read_stealth_weight_food_via_tree_parser()
            
            # 3. 실시간 좌표 및 방향 해독
            pos_x = self.pm.read_int(char_base + 0x0)
            pos_y = self.pm.read_int(char_base + 0x4)
            heading_val = self.pm.read_int(char_base + 0x8)
            
            # 유효성 검사 및 정제
            if hp < 0 or hp > 100000: hp = 0
            if max_hp <= 0: max_hp = 100
            if mp < 0 or mp > 100000: mp = 0
            if max_mp <= 0: max_mp = 100
            if weight < 0 or weight > 100: weight = 0
            if food < 0 or food > 1200: food = 0
            if level < 1 or level > 99: level = 1
            if exp_abs < 0: exp_abs = 0
            if pos_x < 1000 or pos_x > 100000: pos_x = 0
            if pos_y < 1000 or pos_y > 100000: pos_y = 0
            
            hp_pct = (hp / max_hp) * 100.0
            mp_pct = (mp / max_mp) * 100.0
            weight_pct = float(weight)
            
            # 경험치 비율 결정 (순수 메모리 정적 Max EXP 테이블 사용)
            max_exp = self.exp_max_table.get(level, 0)
            if max_exp > 0:
                exp_pct = (exp_abs / float(max_exp)) * 100.0
            else:
                exp_pct = 0.0
                
            if exp_pct > 100.0: exp_pct = 99.9999
            exp_str = f"{exp_pct:.4f}%"
                
            # 방향 매핑
            dir_map = {
                0: "북 ⬆️",
                1: "북동 ↗️",
                2: "동 ➡️",
                3: "남동 ↘️",
                4: "남 ⬇️",
                5: "남서 ↙️",
                6: "서 ⬅️",
                7: "북서 ↖️"
            }
            direction_str = dir_map.get(heading_val, "-")
            
            # 실시간 자가치유 파서 메타데이터 디버그 정보 수집
            strategy = "OFFSET CACHE" if self.cached_offsets["lvl3_wt_off"] > 0 else "TREE SCAN"
            wt_off_hex = hex(self.cached_offsets["lvl3_wt_off"]) if self.cached_offsets["lvl3_wt_off"] > 0 else "-"
            fd_off_hex = hex(self.cached_offsets["lvl3_fd_off"]) if self.cached_offsets["lvl3_fd_off"] > 0 else "-"
            lvl2_off_hex = hex(self.cached_offsets["lvl2_off"]) if self.cached_offsets["lvl2_off"] > 0 else "-"
            
            parser_status = {
                "strategy": strategy,
                "wt_off": wt_off_hex,
                "fd_off": fd_off_hex,
                "lvl2_off": lvl2_off_hex,
                "profile_lvl": self.current_profile_lvl
            }
            
            return {
                "hp": {"percent": hp_pct, "text": f"{hp}/{max_hp}"},
                "mp": {"percent": mp_pct, "text": f"{mp}/{max_mp}"},
                "weight": {"percent": weight_pct, "text": f"{weight}%"},
                "food": {"percent": float(food), "text": f"{food}%"},
                "coords": f"{pos_x}, {pos_y}",
                "direction": direction_str,
                "level": level,
                "exp_abs": exp_abs,
                "exp_pct_str": exp_str,
                "parser_status": parser_status
            }
        except Exception:
            self.pm = None
            return None
