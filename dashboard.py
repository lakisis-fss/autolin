# Enable DPI awareness on Windows to prevent text blurring and layout scaling issues
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

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
from navigator import Navigator

# Smooth color brightening utility for beautiful Bauhaus interactive click/hover effect
def lighten_color(hex_color):
    hex_color = hex_color.lstrip('#')
    lv = len(hex_color)
    if lv == 3:
        hex_color = "".join(2*c for c in hex_color)
    rgb = [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    new_rgb = [min(255, int(c * 1.25)) for c in rgb]
    return f"#{new_rgb[0]:02X}{new_rgb[1]:02X}{new_rgb[2]:02X}"

# Reusable high-fidelity responsive flat button with exquisite hover transitions
def create_flat_button(parent, text, bg_color, click_fn):
    btn = tk.Label(
        parent,
        text=text,
        fg="#F4F1E8",
        bg=bg_color,
        font=("Arial", 9, "bold"),
        relief="flat",
        padx=12,
        pady=6,
        bd=1,
        highlightbackground="#262626",
        highlightthickness=1,
        cursor="hand2"
    )
    def on_enter(e):
        btn.config(bg=lighten_color(bg_color))
    def on_leave(e):
        btn.config(bg=bg_color)
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    btn.bind("<Button-1>", lambda e: click_fn())
    return btn


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
        
        # Monitor Geometry (Floating Window) with smart DPI auto-scaling
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        
        # Calculate process/screen DPI scale factor
        try:
            dpi = self.root.winfo_fpixels('1i')
            self.scale_factor = max(1.0, dpi / 96.0)
        except Exception:
            self.scale_factor = 1.0
            
        self.full_width = int(400 * self.scale_factor)
        self.height = int(850 * self.scale_factor)
        
        x_pos = screen_w - self.full_width - int(50 * self.scale_factor)
        y_pos = (screen_h - self.height) // 2
        
        self.root.geometry(f"{self.full_width}x{self.height}+{x_pos}+{y_pos}")
        self.root.overrideredirect(True) # Borderless
        self.root.attributes("-topmost", True)
        self.root.config(bg=self.colors["bg"])
        
        # State Management
        self.is_minimized = False
        self.min_width = int(40 * self.scale_factor)
        self._dragging = False
        
        # Drag Binding
        self.root.bind("<Button-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.do_drag)
        
        # State Monitor
        self.monitor = state_monitor.StateMonitor()
        self.monitor.start()
        
        self.navigator = Navigator(self.monitor.mem_reader)
        
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
                "path": ["python", "auto_potion_mem.py"], 
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

        # Exit Button (Geometric Circle on Top Right)
        self.exit_btn = tk.Canvas(self.root, width=30, height=30, bg=self.colors["bg"], highlightthickness=0)
        self.exit_btn.place(x=self.full_width - 35, y=5)
        self.exit_btn.create_oval(5, 5, 25, 25, fill=self.colors["red"], outline=self.colors["gray"], width=1)
        self.exit_btn.create_text(15, 15, text="X", fill=self.colors["white"], font=("Arial", 9, "bold"))
        self.exit_btn.bind("<Button-1>", lambda e: self.quit_all())

        # Header (Grid Style)
        header_frame = tk.Frame(self.container, bg=self.colors["bg"], height=100)
        header_frame.pack(fill="x", pady=(20, 10))
        
        title_font = tkfont.Font(family="Arial", size=20, weight="bold")
        sub_font = tkfont.Font(family="Arial", size=10)
        
        tk.Label(header_frame, text="LinclassAuto", fg=self.colors["white"], bg=self.colors["bg"], font=title_font, anchor="w", justify="left", padx=5).pack(anchor="w", padx=30)
        
        # 실시간 캐릭터 좌표 정보 (Bauhaus Yellow 색상으로 사이버네틱 텔레메트리 룩 선사)
        self.coords_lbl = tk.Label(header_frame, text="LOCATION [ 0, 0 ]", fg=self.colors["yellow"], bg=self.colors["bg"], font=("Arial", 10, "bold"), anchor="w", justify="left", padx=5)
        self.coords_lbl.pack(anchor="w", padx=30, pady=(4, 0))
        
        # 메모리 직접 리딩 HP/MP 텔레메트리 (Off White 색상으로 바우하우스 미니멀룩 완성)
        self.mem_lbl = tk.Label(header_frame, text="MEMORY HP [ 0/0 ]  MP [ 0/0 ]", fg=self.colors["white"], bg=self.colors["bg"], font=("Arial", 10, "bold"), anchor="w", justify="left", padx=5)
        self.mem_lbl.pack(anchor="w", padx=30, pady=(4, 0))
        
        # 메모리 직접 리딩 LV/EXP/WT 텔레메트리 (Bauhaus Yellow 색상으로 사이버네틱 텔레메트리 룩 선사, 2줄 구성)
        self.mem_stats_lbl = tk.Label(header_frame, text="MEMORY LV [ 0 ]  EXP [ Calibrating... ]\nMEMORY WT [ 0% ]  FD [ 0% ]", fg=self.colors["yellow"], bg=self.colors["bg"], font=("Arial", 10, "bold"), justify="left", anchor="w", padx=5)
        self.mem_stats_lbl.pack(anchor="w", padx=30, pady=(4, 0))
        
        # Grid/Separator
        tk.Frame(self.container, bg=self.colors["gray"], height=2).pack(fill="x", padx=30, pady=20)
        
        self.create_state_section()
        self.create_navigation_section()
        self.create_heal_test_section()
        self.create_telemetry_parser_section()
        self.create_pipeline_visualizer_section()
        
        # Engine Control Items
        for name, config in self.engines.items():
            self.create_engine_row(name, config)
            
        self.root.after(100, self.update_state_ui)

    def start_drag(self, event):
        # Entry, Canvas(버튼) 클릭 시 드래그 방지
        if isinstance(event.widget, (tk.Entry, tk.Canvas)):
            self._dragging = False
            return
        self._dragging = True
        self.x = event.x
        self.y = event.y

    def do_drag(self, event):
        if not self._dragging:
            return
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
            self.exit_btn.place_forget()
            self.is_minimized = True
        else:
            # Expand and return to original floating width
            new_x = curr_x - self.full_width + self.min_width
            self.root.geometry(f"{self.full_width}x{self.height}+{new_x}+{curr_y}")
            self.container.pack(fill="both", expand=True)
            self.exit_btn.place(x=self.full_width - 35, y=5)
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
            
            # Bauhaus Geometric Cell Frame with thin borders and DPI-friendly height
            cell = tk.Frame(
                self.state_frame, 
                bg="#121212", 
                highlightbackground=self.colors["gray"], 
                highlightthickness=1,
                height=int(56 * self.scale_factor)
            )
            cell.grid(row=item["row"], column=item["col"], sticky="nsew", padx=2, pady=2)
            cell.grid_propagate(False)
            
            # Stat Label (with defensive padding to prevent text clipping)
            lbl = tk.Label(cell, text=item["label"], fg=color, bg="#121212", font=cell_font_label, anchor="w", justify="left", padx=8)
            lbl.pack(side="top", fill="x", pady=(4, 0))
            
            # Stat Value (beautiful vertical alignment)
            val = tk.Label(cell, text="-", fg=self.colors["white"], bg="#121212", font=cell_font_val, anchor="w", justify="left", padx=8)
            val.pack(side="top", fill="x", pady=(2, 0))
            
            self.info_labels[key] = val
            
            # Thin progress bar / line at bottom of cell (DPI responsive)
            if item["is_bar"]:
                # Subtle progress background line
                line_bg = tk.Frame(cell, bg="#1E1E1E", height=2)
                line_bg.pack(side="bottom", fill="x", padx=8, pady=(0, 6))
                
                # Active progress colored line placed relatively within the background container
                line = tk.Frame(line_bg, bg=color, height=2)
                line.place(x=0, y=0, width=0, height=2)
                
                self.cells[key] = {"line": line, "line_bg": line_bg}
                
        # Separator line
        tk.Frame(self.container, bg=self.colors["gray"], height=1).pack(fill="x", padx=30, pady=15)

    def create_navigation_section(self):
        """맵좌표 이동 제어 UI 섹션 (Bauhaus 스타일)"""
        nav_frame = tk.Frame(self.container, bg=self.colors["bg"], padx=30)
        nav_frame.pack(fill="x", pady=(0, 5))

        # Section header (Defensive padding applied)
        tk.Label(nav_frame, text="NAVIGATE", fg=self.colors["yellow"],
                 bg=self.colors["bg"], font=("Arial", 10, "bold"), anchor="w", padx=4).pack(anchor="w")

        # ── 좌표 입력 행 ──
        input_frame = tk.Frame(nav_frame, bg=self.colors["bg"])
        input_frame.pack(fill="x", pady=(5, 5))

        tk.Label(input_frame, text="X", fg=self.colors["text_gray"],
                 bg=self.colors["bg"], font=("Arial", 9, "bold"), anchor="w", padx=4).pack(side="left")

        self.nav_x_entry = tk.Entry(
            input_frame, width=7, bg="#1E1E1E", fg=self.colors["white"],
            insertbackground=self.colors["white"], font=("Arial", 10),
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=self.colors["gray"]
        )
        self.nav_x_entry.pack(side="left", padx=(4, 10))

        tk.Label(input_frame, text="Y", fg=self.colors["text_gray"],
                 bg=self.colors["bg"], font=("Arial", 9, "bold"), anchor="w", padx=4).pack(side="left")

        self.nav_y_entry = tk.Entry(
            input_frame, width=7, bg="#1E1E1E", fg=self.colors["white"],
            insertbackground=self.colors["white"], font=("Arial", 10),
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=self.colors["gray"]
        )
        self.nav_y_entry.pack(side="left", padx=(4, 0))

        # ── 버튼 행 ──
        btn_frame = tk.Frame(nav_frame, bg=self.colors["bg"])
        btn_frame.pack(fill="x", pady=(8, 3))

        # High-fidelity flat buttons that adapt perfectly to scale factor
        go_btn = create_flat_button(btn_frame, "GO", "#2D7D46", self.on_nav_go)
        go_btn.pack(side="left", padx=(0, 6))

        stop_btn = create_flat_button(btn_frame, "STOP", self.colors["red"], self.on_nav_stop)
        stop_btn.pack(side="left", padx=(0, 6))

        cal_btn = create_flat_button(btn_frame, "CALIBRATE", self.colors["blue"], self.on_nav_calibrate)
        cal_btn.pack(side="left")

        # 상태 라벨
        self.nav_status_lbl = tk.Label(
            nav_frame, text="대기 중", fg=self.colors["text_gray"],
            bg=self.colors["bg"], font=("Arial", 8), anchor="w", justify="left", padx=4
        )
        self.nav_status_lbl.pack(anchor="w", pady=(4, 0))

        # Separator
        tk.Frame(self.container, bg=self.colors["gray"], height=1).pack(fill="x", padx=30, pady=10)

    def on_nav_go(self):
        """GO 버튼 핸들러: 입력된 좌표로 이동 시작"""
        try:
            x = int(self.nav_x_entry.get().strip())
            y = int(self.nav_y_entry.get().strip())
            self.navigator.move_to(x, y)
        except ValueError:
            self.nav_status_lbl.config(text="⚠ 올바른 좌표를 입력하세요", fg=self.colors["red"])

    def on_nav_stop(self):
        """STOP 버튼 핸들러: 이동 중단"""
        self.navigator.stop()

    def on_nav_calibrate(self):
        """CALIBRATE 버튼 핸들러: 타일↔픽셀 비율 자동 측정"""
        self.navigator.calibrate()

    def create_heal_test_section(self):
        """힐 스킬 자동 시전 테스트 UI 섹션 (Bauhaus 스타일)"""
        heal_frame = tk.Frame(self.container, bg=self.colors["bg"], padx=30)
        heal_frame.pack(fill="x", pady=(5, 5))

        # Section header (Defensive padding applied)
        tk.Label(heal_frame, text="HEAL CAST TEST", fg=self.colors["yellow"],
                 bg=self.colors["bg"], font=("Arial", 10, "bold"), anchor="w", padx=4).pack(anchor="w")

        # ── 버튼 행 ──
        btn_frame = tk.Frame(heal_frame, bg=self.colors["bg"])
        btn_frame.pack(fill="x", pady=(8, 5))

        # Replaced with gorgeous high-fidelity flat button
        cast_btn = create_flat_button(btn_frame, "CAST HEAL", self.colors["blue"], self.on_cast_heal)
        cast_btn.pack(side="left")

        # 상태 라벨
        self.heal_status_lbl = tk.Label(
            heal_frame, text="대기 중", fg=self.colors["text_gray"],
            bg=self.colors["bg"], font=("Arial", 8), anchor="w", justify="left", padx=4
        )
        self.heal_status_lbl.pack(anchor="w", pady=(4, 0))

        # Separator
        tk.Frame(self.container, bg=self.colors["gray"], height=1).pack(fill="x", padx=30, pady=10)

    def create_telemetry_parser_section(self):
        """실시간 자가치유 파서 상태 모니터링 UI 섹션 (Bauhaus 스타일)"""
        parser_frame = tk.Frame(self.container, bg=self.colors["bg"], padx=30)
        parser_frame.pack(fill="x", pady=(5, 5))
        
        # Section header
        tk.Label(parser_frame, text="SELF-HEALING TELEMETRY", fg=self.colors["yellow"],
                 bg=self.colors["bg"], font=("Arial", 10, "bold"), anchor="w", padx=4).pack(anchor="w")
                 
        # 정보 라벨들을 담을 가로 정렬 바우하우스 박스 프레임
        box = tk.Frame(parser_frame, bg="#121212", highlightbackground=self.colors["gray"], highlightthickness=1)
        box.pack(fill="x", pady=(8, 4))
        
        # 1행: 모드 및 깊이
        row1 = tk.Frame(box, bg="#121212")
        row1.pack(fill="x", padx=8, pady=(6, 3))
        
        tk.Label(row1, text="MEM STATUS:", fg=self.colors["text_gray"], bg="#121212", font=("Arial", 8, "bold")).pack(side="left")
        self.tele_status_lbl = tk.Label(row1, text="CONNECTED", fg="#2D7D46", bg="#121212", font=("Arial", 8, "bold"))
        self.tele_status_lbl.pack(side="left", padx=(4, 15))
        
        tk.Label(row1, text="STRATEGY:", fg=self.colors["text_gray"], bg="#121212", font=("Arial", 8, "bold")).pack(side="left")
        self.tele_strategy_lbl = tk.Label(row1, text="OFFSET CACHE", fg=self.colors["blue"], bg="#121212", font=("Arial", 8, "bold"))
        self.tele_strategy_lbl.pack(side="left", padx=(4, 0))
        
        # 2행: 실시간 무게/포만감 오프셋
        row2 = tk.Frame(box, bg="#121212")
        row2.pack(fill="x", padx=8, pady=(3, 6))
        
        tk.Label(row2, text="WT OFF:", fg=self.colors["text_gray"], bg="#121212", font=("Arial", 8, "bold")).pack(side="left")
        self.tele_wt_lbl = tk.Label(row2, text="-", fg=self.colors["white"], bg="#121212", font=("Arial", 8))
        self.tele_wt_lbl.pack(side="left", padx=(4, 15))
        
        tk.Label(row2, text="FD OFF:", fg=self.colors["text_gray"], bg="#121212", font=("Arial", 8, "bold")).pack(side="left")
        self.tele_fd_lbl = tk.Label(row2, text="-", fg=self.colors["white"], bg="#121212", font=("Arial", 8))
        self.tele_fd_lbl.pack(side="left", padx=(4, 0))
        
        # Separator
        tk.Frame(self.container, bg=self.colors["gray"], height=1).pack(fill="x", padx=30, pady=10)

    def create_pipeline_visualizer_section(self):
        """이원화 데이터 파이프라인 독립성 상태 시각화 위젯 (Bauhaus 스타일)"""
        vis_frame = tk.Frame(self.container, bg=self.colors["bg"], padx=30)
        vis_frame.pack(fill="x", pady=(5, 5))
        
        # Section header
        tk.Label(vis_frame, text="DECOUPLED DATA PIPELINE", fg=self.colors["yellow"],
                 bg=self.colors["bg"], font=("Arial", 10, "bold"), anchor="w", padx=4).pack(anchor="w")
                 
        box = tk.Frame(vis_frame, bg="#121212", highlightbackground=self.colors["gray"], highlightthickness=1)
        box.pack(fill="x", pady=(8, 4))
        
        # 1행: 메모리 파이프라인 인디케이터
        row1 = tk.Frame(box, bg="#121212")
        row1.pack(fill="x", padx=8, pady=(6, 3))
        tk.Label(row1, text="MEM TELEMETRY:", fg=self.colors["text_gray"], bg="#121212", font=("Arial", 8, "bold")).pack(side="left")
        self.pipeline_mem_status = tk.Label(row1, text="[ DIRECT READ ACTIVE ]", fg=self.colors["yellow"], bg="#121212", font=("Arial", 8, "bold"))
        self.pipeline_mem_status.pack(side="left", padx=(4, 0))
        
        # 2행: OCR 파이프라인 인디케이터
        row2 = tk.Frame(box, bg="#121212")
        row2.pack(fill="x", padx=8, pady=(3, 6))
        tk.Label(row2, text="OCR WIDGETS:", fg=self.colors["text_gray"], bg="#121212", font=("Arial", 8, "bold")).pack(side="left")
        self.pipeline_ocr_status = tk.Label(row2, text="[ PURE CV OCR ACTIVE ]", fg=self.colors["blue"], bg="#121212", font=("Arial", 8, "bold"))
        self.pipeline_ocr_status.pack(side="left", padx=(4, 0))
        
        # 3행: 상호 간섭(크로스토크) 감지
        row3 = tk.Frame(box, bg="#121212")
        row3.pack(fill="x", padx=8, pady=(3, 6))
        tk.Label(row3, text="HYBRID LINKAGE:", fg=self.colors["text_gray"], bg="#121212", font=("Arial", 8, "bold")).pack(side="left")
        self.pipeline_linkage = tk.Label(row3, text="DISABLED (100% INDEPENDENT)", fg="#2D7D46", bg="#121212", font=("Arial", 8, "bold"))
        self.pipeline_linkage.pack(side="left", padx=(4, 0))
        
        # Separator
        tk.Frame(self.container, bg=self.colors["gray"], height=1).pack(fill="x", padx=30, pady=10)

    def on_cast_heal(self):
        """힐 시전 테스트 비동기 실행"""
        from heal_caster import HealCaster
        
        def _run():
            self.heal_status_lbl.config(text="🔮 힐 매칭 및 시전 중...", fg=self.colors["yellow"])
            caster = HealCaster(debug=True)
            success, msg = caster.cast_heal()
            if success:
                self.heal_status_lbl.config(text=f"✅ {msg}", fg="#2D7D46")
            else:
                self.heal_status_lbl.config(text=f"❌ {msg}", fg=self.colors["red"])
                
        threading.Thread(target=_run, daemon=True).start()

    def update_bar(self, key, percent, text):
        self.info_labels[key].config(text=text)
        if key in self.cells:
            cell_data = self.cells[key]
            try:
                # Dynamic width computation relative to real screen size
                bg_w = cell_data["line_bg"].winfo_width()
                if bg_w <= 1:
                    bg_w = int(96 * self.scale_factor)
            except Exception:
                bg_w = int(96 * self.scale_factor)
                
            fill_width = max(0, min(bg_w, int(bg_w * (percent / 100.0))))
            cell_data["line"].place(x=0, y=0, width=fill_width, height=2)

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
        
        # 메모리 직접 리딩 HP/MP/레벨/경험치/무게 실시간 업데이트
        mem_hp = state.get("mem_hp", {})
        mem_mp = state.get("mem_mp", {})
        mem_weight = state.get("mem_weight", {})
        mem_food = state.get("mem_food", {})
        mem_level = state.get("mem_level", "0")
        mem_exp_pct = state.get("mem_exp_pct", "Calibrating...")
        
        mem_hp_text = mem_hp.get("text", "0/0")
        mem_mp_text = mem_mp.get("text", "0/0")
        mem_weight_text = mem_weight.get("text", "0%")
        mem_food_text = mem_food.get("text", "0%")
        
        self.mem_lbl.config(text=f"MEMORY HP [ {mem_hp_text} ]  MP [ {mem_mp_text} ]")
        self.mem_stats_lbl.config(text=f"MEMORY LV [ {mem_level} ]  EXP [ {mem_exp_pct} ]\nMEMORY WT [ {mem_weight_text} ]  FD [ {mem_food_text} ]")
        
        # 실시간 자가치유 파서 메타데이터 UI 연동
        parser_status = state.get("parser_status", {})
        strategy = parser_status.get("strategy", "Offline")
        wt_off = parser_status.get("wt_off", "-")
        fd_off = parser_status.get("fd_off", "-")
        
        if strategy == "Offline":
            self.tele_status_lbl.config(text="OFFLINE", fg=self.colors["red"])
            self.tele_strategy_lbl.config(text="DISCONNECTED", fg=self.colors["gray"])
        else:
            self.tele_status_lbl.config(text="CONNECTED", fg="#2D7D46")
            self.tele_strategy_lbl.config(text=strategy)
            if strategy == "TREE SCAN":
                self.tele_strategy_lbl.config(fg=self.colors["yellow"])
            else:
                self.tele_strategy_lbl.config(fg=self.colors["blue"])
                
        self.tele_wt_lbl.config(text=wt_off)
        self.tele_fd_lbl.config(text=fd_off)
        
        # 네비게이션 상태 업데이트
        if hasattr(self, 'nav_status_lbl'):
            self.nav_status_lbl.config(text=self.navigator.status)
            
        # 라이브 파이프라인 시각화 깜빡임 애니메이션 (바우하우스 미학 극대화)
        if hasattr(self, 'pipeline_mem_status') and hasattr(self, 'pipeline_ocr_status'):
            # 0.4초 주기로 점멸 효과
            flash_state = (int(time.time() * 2.5) % 2 == 0)
            if flash_state:
                self.pipeline_mem_status.config(fg=self.colors["yellow"])
                self.pipeline_ocr_status.config(fg=self.colors["blue"])
            else:
                self.pipeline_mem_status.config(fg="#F4F1E8") # Off White
                self.pipeline_ocr_status.config(fg="#F4F1E8") # Off White
        
        self.root.after(200, self.update_state_ui)

    def create_engine_row(self, name, config):
        row_frame = tk.Frame(self.container, bg=self.colors["bg"], padx=30, pady=12)
        row_frame.pack(fill="x")
        
        info_frame = tk.Frame(row_frame, bg=self.colors["bg"])
        info_frame.pack(side="left", fill="x", expand=True)

        # Name Label (Defensive padding applied)
        lbl = tk.Label(info_frame, text=name.upper(), fg=self.colors["white"], bg=self.colors["bg"], 
                      font=("Arial", 14, "bold"), anchor="w", justify="left", padx=4)
        lbl.pack(anchor="w", fill="x")
        
        # Description
        desc_lbl = tk.Label(info_frame, text=config["desc"], fg=self.colors["text_gray"], bg=self.colors["bg"],
                           font=("Arial", 9), anchor="w", justify="left", padx=4)
        desc_lbl.pack(anchor="w", fill="x")
        
        # Status Indicator Canvas styled dynamically with scale factor
        c_size = int(40 * self.scale_factor)
        btn_canvas = tk.Canvas(row_frame, width=c_size, height=c_size, bg=self.colors["bg"], highlightthickness=0)
        btn_canvas.pack(side="right", padx=10)
        
        # Geometric Toggle Button scaled beautifully
        padding = int(5 * self.scale_factor)
        rect_id = btn_canvas.create_rectangle(
            padding, padding, c_size - padding, c_size - padding, 
            fill=self.colors["gray"], outline=self.colors["white"], width=1
        )
        
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
        self.navigator.stop()
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
