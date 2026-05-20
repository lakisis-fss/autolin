import tkinter as tk
from tkinter import font as tkfont
import subprocess
import os
import signal
import sys
import threading
import time
import socket
import state_monitor

class BauhausDashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Spike Lin")
        
        # Design Palette
        self.colors = {
            "bg": "#0D0D0D",      # Midnight Black
            "red": "#E21F26",     # Bauhaus Red
            "yellow": "#F7D117",  # Bauhaus Yellow
            "blue": "#005596",    # Bauhaus Blue
            "gray": "#262626",    # Grid Dark Gray
            "text_gray": "#888888", # Brighter text gray
            "white": "#F4F1E8"    # Off White
        }
        
        # Monitor Geometry (Floating Window)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.full_width = 400
        self.height = 750
        x_pos = screen_w - self.full_width - 50
        y_pos = (screen_h - self.height) // 2
        
        self.root.geometry(f"{self.full_width}x{self.height}+{x_pos}+{y_pos}")
        self.root.overrideredirect(True) # Borderless
        self.root.attributes("-topmost", True)
        self.root.config(bg=self.colors["bg"])
        
        # State Management
        self.is_minimized = False
        self.min_width = 40
        
        # Drag Binding
        self.root.bind("<Button-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.do_drag)
        
        # State Monitor
        self.monitor = state_monitor.StateMonitor()
        self.monitor.start()
        
        self.engines = {
            "PocketBase": {
                "path": ["pocketbase.exe", "serve"], 
                "process": None, 
                "color": self.colors["blue"],
                "desc": "몬스터/아이템 데이터 서버"
            },
            "Monster Engine": {
                "path": ["python", "char_engine.py"], 
                "process": None, 
                "color": self.colors["red"],
                "desc": "실시간 적 인식 및 타겟팅"
            },
            "Auto Potion": {
                "path": ["python", "auto_potion.py"], 
                "process": None, 
                "color": self.colors["yellow"],
                "desc": "HP 감시 및 물약 자동 사용"
            },
        }
        
        self.setup_ui()
        self.update_status_loop()

    def setup_ui(self):
        # Container for main UI to toggle visibility
        self.container = tk.Frame(self.root, bg=self.colors["bg"])
        self.container.pack(fill="both", expand=True)

        # Minimize/Expand Control (Floating Triangle)
        self.toggle_btn = tk.Canvas(self.root, width=30, height=30, bg=self.colors["bg"], highlightthickness=0)
        self.toggle_btn.place(x=5, y=5)
        self.draw_toggle_icon()
        self.toggle_btn.bind("<Button-1>", lambda e: self.toggle_minimize())

        # Header (Grid Style)
        header_frame = tk.Frame(self.container, bg=self.colors["bg"], height=100)
        header_frame.pack(fill="x", pady=(20, 10))
        
        title_font = tkfont.Font(family="Arial", size=20, weight="bold")
        sub_font = tkfont.Font(family="Arial", size=10)
        
        tk.Label(header_frame, text="LinclassAuto", fg=self.colors["white"], bg=self.colors["bg"], font=title_font).pack(anchor="w", padx=30)
        
        # 실시간 캐릭터 좌표 정보 (Bauhaus Yellow 색상으로 사이버네틱 텔레메트리 룩 선사)
        self.coords_lbl = tk.Label(header_frame, text="LOCATION [ 0, 0 ]", fg=self.colors["yellow"], bg=self.colors["bg"], font=("Arial", 10, "bold"))
        self.coords_lbl.pack(anchor="w", padx=30, pady=(4, 0))
        
        # Grid/Separator
        tk.Frame(self.container, bg=self.colors["gray"], height=2).pack(fill="x", padx=30, pady=20)
        
        self.create_state_section()
        
        # Engine Control Items
        for name, config in self.engines.items():
            self.create_engine_row(name, config)
            
        # Exit Button (Geometric Circle)
        exit_canvas = tk.Canvas(self.container, width=60, height=60, bg=self.colors["bg"], highlightthickness=0)
        exit_canvas.pack(side="bottom", pady=40)
        exit_canvas.create_oval(5, 5, 55, 55, fill=self.colors["red"], outline=self.colors["gray"], width=2)
        exit_canvas.bind("<Button-1>", lambda e: self.quit_all())
        tk.Label(self.container, text="CLOSE ALL", fg=self.colors["white"], bg=self.colors["bg"], font=sub_font).pack(side="bottom")
        
        self.root.after(100, self.update_state_ui)

    def start_drag(self, event):
        self.x = event.x
        self.y = event.y

    def do_drag(self, event):
        x = self.root.winfo_x() + (event.x - self.x)
        y = self.root.winfo_y() + (event.y - self.y)
        self.root.geometry(f"+{x}+{y}")

    def draw_toggle_icon(self):
        self.toggle_btn.delete("all")
        if self.is_minimized:
            # Triangle pointing left (to expand)
            self.toggle_btn.create_polygon(25, 5, 25, 25, 10, 15, fill=self.colors["blue"])
        else:
            # Triangle pointing right (to minimize)
            self.toggle_btn.create_polygon(10, 5, 10, 25, 25, 15, fill=self.colors["red"])

    def toggle_minimize(self):
        curr_x = self.root.winfo_x()
        curr_y = self.root.winfo_y()
        if not self.is_minimized:
            # Shrink and keep right-aligned to current position
            new_x = curr_x + self.full_width - self.min_width
            self.root.geometry(f"{self.min_width}x{self.height}+{new_x}+{curr_y}")
            self.container.pack_forget()
            self.is_minimized = True
        else:
            # Expand and return to original floating width
            new_x = curr_x - self.full_width + self.min_width
            self.root.geometry(f"{self.full_width}x{self.height}+{new_x}+{curr_y}")
            self.container.pack(fill="both", expand=True)
            self.is_minimized = False
        self.draw_toggle_icon()

    def create_state_section(self):
        self.state_frame = tk.Frame(self.container, bg=self.colors["bg"])
        self.state_frame.pack(fill="x", padx=30, pady=(0, 10))
        
        # Grid Configuration (3x3 Bauhaus Grid Layout)
        self.cells = {}
        self.info_labels = {}
        
        grid_data = [
            # Row 0
            {"key": "hp",     "label": "HP",     "color": "#E21F26", "is_bar": True,  "row": 0, "col": 0},
            {"key": "mp",     "label": "MP",     "color": "#3C82F6", "is_bar": True,  "row": 0, "col": 1},
            {"key": "weight", "label": "WEIGHT", "color": "#F59E0B", "is_bar": True,  "row": 0, "col": 2},
            # Row 1
            {"key": "레벨",   "label": "LEVEL",  "color": "#888888", "is_bar": False, "row": 1, "col": 0},
            {"key": "경험치", "label": "EXP",    "color": "#888888", "is_bar": False, "row": 1, "col": 1},
            {"key": "AC",     "label": "AC",     "color": "#888888", "is_bar": False, "row": 1, "col": 2},
            # Row 2
            {"key": "MR",     "label": "MR",     "color": "#888888", "is_bar": False, "row": 2, "col": 0},
            {"key": "포만감", "label": "FOOD",   "color": "#888888", "is_bar": False, "row": 2, "col": 1},
            {"key": "성향치", "label": "LAWFUL", "color": "#888888", "is_bar": False, "row": 2, "col": 2}
        ]
        
        # Grid Column weights
        for c in range(3):
            self.state_frame.grid_columnconfigure(c, weight=1, uniform="equal")
            
        cell_font_label = tkfont.Font(family="Arial", size=8, weight="bold")
        cell_font_val = tkfont.Font(family="Arial", size=9, weight="bold")
        
        for item in grid_data:
            key = item["key"]
            color = item["color"]
            
            # Bauhaus Geometric Cell Frame with thin borders
            cell = tk.Frame(
                self.state_frame, 
                bg="#121212", 
                highlightbackground=self.colors["gray"], 
                highlightthickness=1,
                height=48
            )
            cell.grid(row=item["row"], column=item["col"], sticky="nsew", padx=2, pady=2)
            cell.grid_propagate(False)
            
            # Stat Label (top-left)
            lbl = tk.Label(cell, text=item["label"], fg=color, bg="#121212", font=cell_font_label)
            lbl.place(x=8, y=4)
            
            # Stat Value (aligned nicely)
            val = tk.Label(cell, text="-", fg=self.colors["white"], bg="#121212", font=cell_font_val)
            val.place(x=8, y=20)
            
            self.info_labels[key] = val
            
            # Thin progress bar / line at bottom of cell
            if item["is_bar"]:
                # Subtle progress background line
                line_bg = tk.Frame(cell, bg="#1E1E1E", height=2)
                line_bg.place(x=8, y=40, width=96, height=2)
                
                # Active progress colored line
                line = tk.Frame(cell, bg=color, height=2)
                line.place(x=8, y=40, width=0, height=2)
                
                self.cells[key] = {"line": line}
                
        # Separator line
        tk.Frame(self.container, bg=self.colors["gray"], height=1).pack(fill="x", padx=30, pady=15)

    def update_bar(self, key, percent, text):
        self.info_labels[key].config(text=text)
        if key in self.cells:
            cell_data = self.cells[key]
            # Since cell active width of progress line is 96 pixels:
            cell_width = 96
            fill_width = max(0, min(cell_width, int(cell_width * (percent / 100.0))))
            cell_data["line"].place(x=8, y=40, width=fill_width, height=2)

    def update_state_ui(self):
        state = self.monitor.get_state()
        
        hp = state.get("hp", {})
        hp_pct = hp.get("percent", 0.0)
        hp_text = hp.get("text", "0/0")
        self.update_bar("hp", hp_pct, hp_text)
        
        mp = state.get("mp", {})
        mp_pct = mp.get("percent", 0.0)
        mp_text = mp.get("text", "0/0")
        self.update_bar("mp", mp_pct, mp_text)
        
        weight = state.get("weight", {})
        weight_pct = weight.get("percent", 0.0)
        weight_text = weight.get("text", "0%")
        self.update_bar("weight", weight_pct, weight_text)
        
        self.info_labels["레벨"].config(text=state.get("level", "0"))
        self.info_labels["경험치"].config(text=state.get("exp", "0%"))
        self.info_labels["AC"].config(text=state.get("ac", "0"))
        self.info_labels["MR"].config(text=state.get("mr", "0%"))
        self.info_labels["포만감"].config(text=state.get("food", "0%"))
        self.info_labels["성향치"].config(text=state.get("lawful", "0"))
        
        # 실시간 좌표값 및 방향 업데이트
        coords_text = state.get("coords", "0, 0")
        direction_text = state.get("direction", "-")
        self.coords_lbl.config(text=f"LOCATION [ {coords_text} ]  {direction_text}")
        
        self.root.after(200, self.update_state_ui)

    def create_engine_row(self, name, config):
        row_frame = tk.Frame(self.container, bg=self.colors["bg"], padx=30, pady=15)
        row_frame.pack(fill="x")
        
        info_frame = tk.Frame(row_frame, bg=self.colors["bg"])
        info_frame.pack(side="left")

        # Name Label
        lbl = tk.Label(info_frame, text=name.upper(), fg=self.colors["white"], bg=self.colors["bg"], 
                      font=("Arial", 14, "bold"), anchor="w")
        lbl.pack(anchor="w")
        
        # Description
        desc_lbl = tk.Label(info_frame, text=config["desc"], fg=self.colors["text_gray"], bg=self.colors["bg"],
                           font=("Arial", 9), anchor="w")
        desc_lbl.pack(anchor="w")
        
        # Status Indicator (Yellow Circle initially)
        btn_canvas = tk.Canvas(row_frame, width=40, height=40, bg=self.colors["bg"], highlightthickness=0)
        btn_canvas.pack(side="right", padx=10)
        
        # Geometric Toggle Button (Bauhaus Square/Circle)
        rect_id = btn_canvas.create_rectangle(5, 5, 35, 35, fill=self.colors["gray"], outline=self.colors["white"], width=1)
        
        config["canvas"] = btn_canvas
        config["shape"] = rect_id
        
        btn_canvas.bind("<Button-1>", lambda e: self.toggle_engine(name))

    def toggle_engine(self, name):
        config = self.engines[name]
        if config["process"] is None:
            # Start Process
            try:
                # Use CREATE_NEW_PROCESS_GROUP on Windows if needed, but standard popen usually fine
                config["process"] = subprocess.Popen(config["path"], shell=True)
                config["canvas"].itemconfig(config["shape"], fill=config["color"])
                print(f"Started: {name}")
            except Exception as e:
                print(f"Failed to start {name}: {e}")
        else:
            # Stop Process
            try:
                # config["process"].terminate() # Friendly stop
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(config['process'].pid)]) # Force stop tree
                config["process"] = None
                config["canvas"].itemconfig(config["shape"], fill=self.colors["gray"])
                print(f"Stopped: {name}")
            except Exception as e:
                print(f"Failed to stop {name}: {e}")

    def check_port(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    def update_status_loop(self):
        # Background loop to check if processes are still alive
        def check():
            while True:
                for name, config in self.engines.items():
                    # Special check for PocketBase port
                    if name == "PocketBase":
                        if self.check_port(8090):
                            # Mark as active if port is open, even without process object
                            config["canvas"].itemconfig(config["shape"], fill=config["color"])
                        else:
                            if config["process"] is None:
                                config["canvas"].itemconfig(config["shape"], fill=self.colors["gray"])
                    
                    if config["process"] is not None:
                        if config["process"].poll() is not None: # Finished/Crashed
                            config["process"] = None
                            if name != "PocketBase": # Special case above
                                config["canvas"].itemconfig(config["shape"], fill=self.colors["gray"])
                time.sleep(1)
        
        t = threading.Thread(target=check, daemon=True)
        t.start()

    def quit_all(self):
        self.monitor.stop()
        for name, config in self.engines.items():
            if config["process"] is not None:
                try:
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(config['process'].pid)])
                except:
                    pass
        self.root.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = BauhausDashboard()
    app.root.mainloop()
