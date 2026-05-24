import time
import threading
import re
from cv_state_reader import CVStateReader
from mem_state_reader import MemStateReader

class StateMonitor:
    def __init__(self):
        self.state = {
            "hp": {"percent": 0.0, "text": "0%"},
            "mp": {"percent": 0.0, "text": "0%"},
            "mem_hp": {"percent": 0.0, "text": "0/0"},
            "mem_mp": {"percent": 0.0, "text": "0/0"},
            "mem_weight": {"percent": 0.0, "text": "0%"},
            "mem_food": {"percent": 0.0, "text": "0%"},
            "weight": {"percent": 0.0, "text": "0%"},
            "level": "0",
            "exp": "0%",
            "mem_level": "0",
            "mem_exp_abs": "0",
            "mem_exp_pct": "Calibrating...",
            "ac": "0",
            "mr": "0%",
            "food": "0%",
            "lawful": "0",
            "map": "?",
            "coords": "0, 0",
            "direction": "?",
            "transform": "?",
            "debuffs": "?",
            "parser_status": {
                "strategy": "Scan...",
                "wt_off": "-",
                "fd_off": "-",
                "lvl2_off": "-",
                "profile_lvl": 14
            }
        }
        self.running = False
        self.thread = None
        self.reader = CVStateReader(debug=True)
        self.mem_reader = MemStateReader()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def get_state(self):
        return self.state

    def _loop(self):
        while self.running:
            try:
                # 1. 이미지 인식에서 상태 읽기
                mem_data = self.reader.get_state()
                if mem_data:
                    self.state["hp"]["percent"] = mem_data["hp"]["percent"]
                    self.state["hp"]["text"] = mem_data["hp"].get("text", "")
                    
                    self.state["mp"]["percent"] = mem_data["mp"]["percent"]
                    self.state["mp"]["text"] = mem_data["mp"].get("text", "")
                    
                    self.state["weight"]["percent"] = mem_data["weight"]["percent"]
                    self.state["weight"]["text"] = mem_data["weight"].get("text", "")
                    
                    self.state["level"] = mem_data.get("level", "0")
                    self.state["exp"] = mem_data.get("exp", "0%")
                    self.state["ac"] = mem_data.get("ac", "0")
                    self.state["mr"] = mem_data.get("mr", "0%")
                    self.state["food"] = mem_data.get("food", "0%")
                    self.state["lawful"] = mem_data.get("lawful", "0")
                
                # 2. 메모리에서 실시간 좌표 및 HP/MP/LEVEL/EXP 읽기 (완벽하게 독립적으로 상호 참조 없이 작동)
                coords_data = self.mem_reader.get_state()
                if coords_data:
                    # [지능형 자가 최적화 캘리브레이션 복원]
                    # 상단 메모리 추출 수치가 참값에 수렴하도록 메모리 자체 환산 배율만 독립적으로 교정합니다.
                    # (하단 그리드를 강제 덮어쓰기 보정하던 연동 코드는 절대 복원하지 않고 이원화 유지를 보장합니다.)
                    if mem_data and mem_data.get("exp"):
                        self.mem_reader.update_exp_calibration(mem_data["exp"], coords_data["level"])

                    self.state["coords"] = coords_data.get("coords", "0, 0")
                    self.state["direction"] = coords_data.get("direction", "-")
                    self.state["mem_hp"] = coords_data.get("hp", {"percent": 0.0, "text": "0/0"})
                    self.state["mem_mp"] = coords_data.get("mp", {"percent": 0.0, "text": "0/0"})
                    self.state["mem_weight"] = coords_data.get("weight", {"percent": 0.0, "text": "0%"})
                    self.state["mem_food"] = coords_data.get("food", {"percent": 0.0, "text": "0%"})
                    self.state["parser_status"] = coords_data.get("parser_status", {})
                    
                    # 메모리 직접 리딩 정보 연동 (대시보드 상단 텔레메트리 전용)
                    self.state["mem_level"] = str(coords_data["level"])
                    self.state["mem_exp_abs"] = str(coords_data["exp_abs"])
                    self.state["mem_exp_pct"] = coords_data["exp_pct_str"]
                    
                    # [이원화 핵심 보장]
                    # 하단 그리드 셀(exp, level, weight, food)을 메모리 값으로 강제 보정(덮어쓰기)하던 
                    # 하이브리드 보정 코드를 전면 제거하여 OCR 판독 결과 그대로 독립 표기하도록 유지합니다.
                else:
                    self.state["coords"] = "0, 0"
                    self.state["direction"] = "-"
                    self.state["mem_hp"] = {"percent": 0.0, "text": "0/0"}
                    self.state["mem_mp"] = {"percent": 0.0, "text": "0/0"}
                    self.state["mem_weight"] = {"percent": 0.0, "text": "0%"}
                    self.state["mem_food"] = {"percent": 0.0, "text": "0%"}
                    self.state["mem_level"] = "0"
                    self.state["mem_exp_abs"] = "0"
                    self.state["mem_exp_pct"] = "Calibrating..."
                    self.state["parser_status"] = {
                        "strategy": "Offline",
                        "wt_off": "-",
                        "fd_off": "-",
                        "lvl2_off": "-",
                        "profile_lvl": 0
                    }
                    
                self.state["map"] = "Scan..."
                self.state["transform"] = "-"
                self.state["debuffs"] = "-"
            except Exception as e:
                print(f"[StateMonitor] Error in _loop: {e}")
            
            time.sleep(0.5) # 0.5초 주기로 스캔
