import pymem
import pymem.process
import time

class MemStateReader:
    def __init__(self, process_name="LC.exe"):
        self.process_name = process_name
        self.pm = None
        self.base_address = 0
        # HP 오프셋: 0x143603c (검증됨)
        # 주변 4바이트 간격으로 MaxHP, MP, MaxMP가 위치할 가능성이 높음
        self.offsets = {
            "hp": 0x143603c,
            "max_hp": 0x1436040, 
            "mp": 0x1436044,
            "max_mp": 0x1436048,
            "weight": 0x143604C,
            "pos_x": 0x149b350,  # [검증됨] 실시간 절대 X좌표 오프셋
            "pos_y": 0x149b354,  # [검증됨] 실시간 절대 Y좌표 오프셋
            "heading": 0x149b358 # [검증됨] 실시간 캐릭터 방향 오프셋
        }
        self.last_attach_attempt = 0

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

    def get_state(self):
        if not self.pm:
            if not self.attach():
                return None

        try:
            hp = self.pm.read_int(self.base_address + self.offsets["hp"])
            max_hp = self.pm.read_int(self.base_address + self.offsets["max_hp"])
            mp = self.pm.read_int(self.base_address + self.offsets["mp"])
            max_mp = self.pm.read_int(self.base_address + self.offsets["max_mp"])
            
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
            
            # 리니지 기본 타일 좌표 범위 검사 (비정상 값 방지)
            if pos_x < 1000 or pos_x > 100000: pos_x = 0
            if pos_y < 1000 or pos_y > 100000: pos_y = 0
            
            hp_pct = (hp / max_hp) * 100.0
            mp_pct = (mp / max_mp) * 100.0
            
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
                "weight": {"percent": 0.0, "text": "Memory Mode"}, # 무게는 추후 탐색
                "coords": f"{pos_x}, {pos_y}",
                "direction": direction_str
            }
        except Exception:
            self.pm = None # 연결 끊김 처리
            return None
