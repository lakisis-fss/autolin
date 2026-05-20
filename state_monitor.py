import time
import threading
from cv_state_reader import CVStateReader
from mem_state_reader import MemStateReader

class StateMonitor:
    def __init__(self):
        self.state = {
            "hp": {"percent": 0.0, "text": "0%"},
            "mp": {"percent": 0.0, "text": "0%"},
            "weight": {"percent": 0.0, "text": "0%"},
            "level": "0",
            "exp": "0%",
            "ac": "0",
            "mr": "0%",
            "food": "0%",
            "lawful": "0",
            "map": "?",
            "coords": "0, 0",
            "direction": "?",
            "transform": "?",
            "debuffs": "?"
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
                
                # 2. 메모리에서 실시간 좌표 읽기
                coords_data = self.mem_reader.get_state()
                if coords_data:
                    self.state["coords"] = coords_data.get("coords", "0, 0")
                    self.state["direction"] = coords_data.get("direction", "-")
                else:
                    self.state["coords"] = "0, 0"
                    self.state["direction"] = "-"
                    
                self.state["map"] = "Scan..."
                self.state["transform"] = "-"
                self.state["debuffs"] = "-"
            except Exception as e:
                print(f"[StateMonitor] Error in _loop: {e}")
            
            time.sleep(0.5) # 0.5초 주기로 스캔
