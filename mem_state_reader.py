import pymem
import pymem.process
import time
import re

class MemStateReader:
    def __init__(self, process_name="LC.exe"):
        self.process_name = process_name
        self.pm = None
        self.base_address = 0
        # 캐릭터 상태 구조체 오프셋 정밀 스캔 완료 (좌표 오프셋 0x149b350 뒤로 연속 배치됨)
        self.offsets = {
            "pos_x": 0x149b350,   # [검증됨] 실시간 절대 X좌표 오프셋
            "pos_y": 0x149b354,   # [검증됨] 실시간 절대 Y좌표 오프셋
            "heading": 0x149b358, # [검증됨] 실시간 캐릭터 방향 오프셋
            "hp": 0x149b35c,      # [검증됨] 실시간 절대 HP 오프셋 (149b350 + 12)
            "max_hp": 0x149b360,  # [검증됨] 실시간 절대 MaxHP 오프셋 (149b350 + 16)
            "mp": 0x149b364,      # [검증됨] 실시간 절대 MP 오프셋 (149b350 + 20)
            "max_mp": 0x149b368,  # [검증됨] 실시간 절대 MaxMP 오프셋 (149b350 + 24)
            "level": 0x149b36c,   # [검증됨] 실시간 캐릭터 레벨 오프셋 (149b350 + 28)
            "weight": 0x1460730,  # [검증됨] 정적 세그먼트 무게% 오프셋 (35% 고정)
            "food": 0x1460740,    # [검증됨] 정적 세그먼트 포만감% 오프셋
            "exp_abs": 0x149b378  # [검증됨] 실시간 절대 경험치값 오프셋 (149b350 + 40)
        }
        self.last_attach_attempt = 0
        
        # 골든 포인터 체인 자동 자가치유용 오프셋 및 상태 초기화
        self.weight_chain = {
            "lvl1_off": 0x710,
            "lvl2_off": 0xb28,
            "lvl3_wt_off": 0x1474,
            "lvl3_fd_off": 0x14f4
        }
        self.last_heal_attempt = 0
        
        # 하이브리드 경험치 캘리브레이션 상태 정보
        self.exp_ratio = 1.4123283281076878e-05  # 레벨 14 진짜 정밀 경험치 배율 프리셋 (62.3190% / 4412501)
        self.calibrated_level = 14

    def attach(self):
        # 5초마다 재연결 시도
        if time.time() - self.last_attach_attempt < 5:
            return False
        self.last_attach_attempt = time.time()
        
        try:
            self.pm = pymem.Pymem(self.process_name)
            module = pymem.process.module_from_name(self.pm.process_handle, self.process_name)
            self.base_address = module.lpBaseOfDll
            return True
        except Exception:
            return False

    def update_exp_calibration(self, ocr_exp_str, current_level):
        """OCR로 읽은 정상 범위의 경험치% 문자열을 기반으로 메모리 경험치 환산 배율 캘리브레이션"""
        if not ocr_exp_str or "%" not in ocr_exp_str:
            return
            
        # 레벨 14는 한 치의 오차도 없는 완벽한 배율이 프리셋팅되어 있으므로 OCR 오독에 의한 왜곡 방지
        if current_level == 14:
            return
            
        # 정밀 검증용 정규식: 소수점 4자리 형태인 경우에만 정밀 캘리브레이션 인정 (예: 59.3750%)
        # 간혹 OCR 오류로 소수점이 없거나 자리수가 다르면 배율이 왜곡되므로 차단
        match = re.search(r"(\d{1,2}\.\d{4})%", ocr_exp_str)
        if not match:
            return
        
        try:
            ocr_val = float(match.group(1))
            
            # 비정상적인 값(이상치) 필터링
            if ocr_val <= 0.0 or ocr_val >= 100.0:
                return
                
            # 현재 메모리상의 절대 경험치량
            if not self.pm:
                return
            exp_abs = self.pm.read_int(self.base_address + self.offsets["exp_abs"])
            
            if exp_abs > 0:
                new_ratio = ocr_val / float(exp_abs)
                
                # 기존 캘리브레이션이 존재하고, 동일 레벨이라면
                # 급격한 캘리브레이션 변동(오타)은 노이즈로 간주하고 업데이트 차단
                if self.exp_ratio > 0.0 and self.calibrated_level == current_level:
                    ratio_diff = abs(new_ratio - self.exp_ratio) / self.exp_ratio
                    if ratio_diff > 0.05: # 5% 이상의 변동은 오염으로 보고 무시
                        return
                
                self.exp_ratio = new_ratio
                self.calibrated_level = current_level
                print(f"[MemStateReader] Exp Calibration Completed. Ratio: {self.exp_ratio:.8e} at Level {current_level}")
        except Exception as e:
            print(f"[MemStateReader] Calibration error: {e}")

    def heal_weight_chain(self, target_weight=35):
        """힙 재할당 시 실시간 무게와 포만감을 탐색하여 체인 오프셋을 자동 복구하는 자가치유 로직"""
        if not self.pm:
            return False
        try:
            char_base = self.base_address + 0x149b350
            lvl1 = self.pm.read_longlong(char_base + 0xb0)
            if lvl1 <= 0:
                return False
                
            lvl2_addr = self.pm.read_longlong(lvl1 + self.weight_chain["lvl1_off"])
            if lvl2_addr <= 0:
                return False
                
            if target_weight < 0 or target_weight > 100:
                target_weight = 35
                
            # 0.05초 대역 고속 탐색
            for off2 in range(0, 0x1800, 8):
                try:
                    lvl3_addr = self.pm.read_longlong(lvl2_addr + off2)
                    if not (0x10000000000 < lvl3_addr < 0x7ffffffffff):
                        continue
                    for off3 in range(0, 0x3000, 4):
                        try:
                            w_val = self.pm.read_int(lvl3_addr + off3)
                            if w_val == target_weight:
                                # 무게 발견 시 주변 ±256 바이트 이내에서 포만감(500~990) 탐색
                                for near_off in range(off3 - 256, off3 + 256, 4):
                                    if near_off < 0 or near_off >= 0x3000 or near_off == off3:
                                        continue
                                    try:
                                        f_val = self.pm.read_int(lvl3_addr + near_off)
                                        if 500 <= f_val <= 990:
                                            self.weight_chain["lvl2_off"] = off2
                                            self.weight_chain["lvl3_wt_off"] = off3
                                            self.weight_chain["lvl3_fd_off"] = near_off
                                            print(f"[MemStateReader] [Self-Healing] Updated offsets: lvl2+{hex(off2)} -> lvl3+{hex(off3)}(Wt) / {hex(near_off)}(Fd:{f_val})")
                                            return True
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception as e:
            print(f"[MemStateReader] [Self-Healing] Error: {e}")
        return False

    def get_state(self):
        if not self.pm:
            if not self.attach():
                return None

        try:
            hp = self.pm.read_int(self.base_address + self.offsets["hp"])
            max_hp = self.pm.read_int(self.base_address + self.offsets["max_hp"])
            mp = self.pm.read_int(self.base_address + self.offsets["mp"])
            max_mp = self.pm.read_int(self.base_address + self.offsets["max_mp"])
            # 실시간 동적 포인터 체인을 통한 weight 및 food 리딩 (자가치유 활성화)
            weight = 0
            food = 0
            try:
                char_base = self.base_address + 0x149b350
                lvl1 = self.pm.read_longlong(char_base + 0xb0)
                if lvl1 > 0:
                    lvl2 = self.pm.read_longlong(lvl1 + self.weight_chain["lvl1_off"])
                    if lvl2 > 0:
                        lvl3 = self.pm.read_longlong(lvl2 + self.weight_chain["lvl2_off"])
                        if lvl3 > 0:
                            weight = self.pm.read_int(lvl3 + self.weight_chain["lvl3_wt_off"])
                            food = self.pm.read_int(lvl3 + self.weight_chain["lvl3_fd_off"])
                            
                # 리딩 실패 혹은 힙 재할당으로 깨진 경우 자가치유 가동
                if weight <= 0 or food <= 0 or weight > 100 or food > 1000:
                    current_time = time.time()
                    if current_time - self.last_heal_attempt > 3: # 3초 쿨타임
                        self.last_heal_attempt = current_time
                        self.heal_weight_chain(target_weight=35)
                        # 자가치유 완료 후 재차 읽기
                        lvl2 = self.pm.read_longlong(lvl1 + self.weight_chain["lvl1_off"])
                        if lvl2 > 0:
                            lvl3 = self.pm.read_longlong(lvl2 + self.weight_chain["lvl2_off"])
                            if lvl3 > 0:
                                weight = self.pm.read_int(lvl3 + self.weight_chain["lvl3_wt_off"])
                                food = self.pm.read_int(lvl3 + self.weight_chain["lvl3_fd_off"])
            except Exception:
                pass
            level = self.pm.read_int(self.base_address + self.offsets["level"])
            exp_abs = self.pm.read_int(self.base_address + self.offsets["exp_abs"])
            
            # 실시간 좌표 리딩 (4바이트 정수형)
            pos_x = self.pm.read_int(self.base_address + self.offsets["pos_x"])
            pos_y = self.pm.read_int(self.base_address + self.offsets["pos_y"])
            
            # 실시간 캐릭터 방향 리딩 (0~7 정수형)
            heading_val = self.pm.read_int(self.base_address + self.offsets["heading"])
            
            # 유효성 검사 (말도 안되는 값이면 무시)
            if hp < 0 or hp > 100000: hp = 0
            if max_hp <= 0: max_hp = 100
            if mp < 0 or mp > 100000: mp = 0
            if max_mp <= 0: max_mp = 100
            if weight < 0 or weight > 100: weight = 0
            if food < 0 or food > 1000: food = 0
            if level < 1 or level > 99: level = 1
            if exp_abs < 0: exp_abs = 0
            
            # 리니지 기본 타일 좌표 범위 검사 (비정상 값 방지)
            if pos_x < 1000 or pos_x > 100000: pos_x = 0
            if pos_y < 1000 or pos_y > 100000: pos_y = 0
            
            hp_pct = (hp / max_hp) * 100.0
            mp_pct = (mp / max_mp) * 100.0
            weight_pct = float(weight)
            
            # 하이브리드 경험치 계산
            # 레벨이 바뀌면 비율 재교정이 필요하므로 레벨 불일치 체크
            if self.calibrated_level != level:
                self.exp_ratio = 0.0 # 초기화 후 재교정 유도
                
            if self.exp_ratio > 0.0:
                exp_pct = exp_abs * self.exp_ratio
                # 상한선 보정
                if exp_pct > 100.0: exp_pct = 99.9999
                exp_str = f"{exp_pct:.4f}%"
            else:
                # 캘리브레이션 전에는 정밀 표시 보류
                exp_str = "Calibrating..."
            
            # 전통적인 8방향 한글화 및 미려한 유니코드 화살표 매핑
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
            
            return {
                "hp": {"percent": hp_pct, "text": f"{hp}/{max_hp}"},
                "mp": {"percent": mp_pct, "text": f"{mp}/{max_mp}"},
                "weight": {"percent": weight_pct, "text": f"{weight}%"},
                "food": {"percent": food / 10.0, "text": f"{int(food / 10.0)}%"},
                "coords": f"{pos_x}, {pos_y}",
                "direction": direction_str,
                "level": level,
                "exp_abs": exp_abs,
                "exp_pct_str": exp_str
            }
        except Exception:
            self.pm = None # 연결 끊김 처리
            return None

