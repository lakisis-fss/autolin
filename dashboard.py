import tkinter as tk
from tkinter import font as tkfont
import subprocess
import os
import signal
import sys
import threading
import time
import socket

class BauhausDashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("BAUHAUS COCKPIT")
        
        # Design Palette
        self.colors = {
            "bg": "#0D0D0D",      # Midnight Black
            "red": "#E21F26",     # Bauhaus Red
            "yellow": "#F7D117",  # Bauhaus Yellow
            "blue": "#005596",    # Bauhaus Blue
            "gray": "#262626",    # Grid Dark Gray
            "white": "#F4F1E8"    # Off White
        }
        
        # Monitor Geometry (Right 1/4)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = screen_w // 4
        x_pos = screen_w - width
        self.root.geometry(f"{width}x{screen_h}+{x_pos}+0")
        self.root.overrideredirect(True) # Borderless
        self.root.attributes("-topmost", True)
        self.root.config(bg=self.colors["bg"])
        
        # State Management
        self.is_minimized = False
        self.full_width = screen_w // 4
        self.min_width = 40
        self.height = screen_h
        self.x_pos = screen_w - self.full_width
        
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
        
        title_font = tkfont.Font(family="Arial", size=24, weight="bold")
        sub_font = tkfont.Font(family="Arial", size=10)
        
        tk.Label(header_frame, text="ARCHIVE", fg=self.colors["blue"], bg=self.colors["bg"], font=sub_font).pack(anchor="w", padx=30)
        tk.Label(header_frame, text="BAUHAUS", fg=self.colors["white"], bg=self.colors["bg"], font=title_font).pack(anchor="w", padx=30)
        tk.Label(header_frame, text="ENGINE COCKPIT", fg=self.colors["red"], bg=self.container["bg"], font=sub_font).pack(anchor="w", padx=30)
        
        # Grid/Separator
        tk.Frame(self.container, bg=self.colors["gray"], height=2).pack(fill="x", padx=30, pady=20)
        
        # Engine Control Items
        for name, config in self.engines.items():
            self.create_engine_row(name, config)
            
        # Exit Button (Geometric Circle)
        exit_canvas = tk.Canvas(self.container, width=60, height=60, bg=self.colors["bg"], highlightthickness=0)
        exit_canvas.pack(side="bottom", pady=40)
        exit_canvas.create_oval(5, 5, 55, 55, fill=self.colors["red"], outline=self.colors["gray"], width=2)
        exit_canvas.bind("<Button-1>", lambda e: self.quit_all())
        tk.Label(self.container, text="CLOSE ALL", fg=self.colors["white"], bg=self.colors["bg"], font=sub_font).pack(side="bottom")

    def draw_toggle_icon(self):
        self.toggle_btn.delete("all")
        if self.is_minimized:
            # Triangle pointing left
            self.toggle_btn.create_polygon(10, 5, 10, 25, 25, 15, fill=self.colors["blue"])
        else:
            # Triangle pointing right
            self.toggle_btn.create_polygon(25, 5, 25, 25, 10, 15, fill=self.colors["red"])

    def toggle_minimize(self):
        screen_w = self.root.winfo_screenwidth()
        if not self.is_minimized:
            self.root.geometry(f"{self.min_width}x{self.height}+{screen_w - self.min_width}+0")
            self.container.pack_forget()
            self.is_minimized = True
        else:
            self.root.geometry(f"{self.full_width}x{self.height}+{screen_w - self.full_width}+0")
            self.container.pack(fill="both", expand=True)
            self.is_minimized = False
        self.draw_toggle_icon()

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
        desc_lbl = tk.Label(info_frame, text=config["desc"], fg=self.colors["gray"], bg=self.colors["bg"],
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
