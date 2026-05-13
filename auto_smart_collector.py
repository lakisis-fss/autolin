import pymem
import pymem.process
import keyboard
import time
import ctypes
import struct
import tkinter as tk
import mss
import pydirectinput
import os
import uuid
from threading import Thread, Lock

# Windows Constants & DPI Awareness
MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # DPI_Awareness_Per_Monitor
except:
    ctypes.windll.user32.SetProcessDPIAware() # Fallback for older Windows

class SmartCollector:
    def __init__(self, process_name="LC.exe"):
        self.process_name = process_name
        self.pm = None
        self.potential_addresses = []
        self.last_values = {}
        self.target_address = None
        self.is_active = False
        self.lock = Lock()
        
        self.save_dir = "datasets/raw/monster_samples"
        self.crop_size = 250
        self.first_capture = True # For diagnostic full-screen shot
        
        # Overlay UI (Solid Visibility Upgrade)
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        # self.root.attributes("-transparentcolor", "black") # Disabled for visibility
        self.root.config(bg="#222222", bd=2, relief="solid") # Dark grey with border
        self.root.geometry("300x120+15+15") # Top-left corner
        
        self.status_label = tk.Label(self.root, text="[F9] START COLLECTING", fg="#CCCCCC", bg="#222222", font=("Arial", 9, "bold"))
        self.status_label.pack(anchor="w", padx=5)
        
        self.msg_label = tk.Label(self.root, text="READY", fg="#00FF00", bg="#222222", font=("Arial", 14, "bold"))
        self.msg_label.pack(anchor="w", padx=5)
        
        self.count_label = tk.Label(self.root, text="Matches: 0", fg="#FFFF00", bg="#222222", font=("Arial", 10, "bold"))
        self.count_label.pack(anchor="w", padx=5)
        
        self.heartbeat = False

    def attach(self):
        try:
            self.pm = pymem.Pymem(self.process_name)
            return True
        except:
            self.msg_label.config(text="ERROR: Attach Failed", fg="red")
            return False

    def get_memory_pages(self):
        pages = []
        address = 0
        kernel32 = ctypes.windll.kernel32
        class MBI64(ctypes.Structure):
            _fields_ = [("BaseAddress", ctypes.c_uint64), ("AllocationBase", ctypes.c_uint64), ("AllocationProtect", ctypes.c_uint32), ("Alignment1", ctypes.c_uint32), ("RegionSize", ctypes.c_uint64), ("State", ctypes.c_uint32), ("Protect", ctypes.c_uint32), ("Type", ctypes.c_uint32), ("Alignment2", ctypes.c_uint32)]
        mbi = MBI64(); size = ctypes.sizeof(mbi)
        while kernel32.VirtualQueryEx(self.pm.process_handle, ctypes.c_void_p(address), ctypes.byref(mbi), size):
            if mbi.State == MEM_COMMIT and (mbi.Protect & (PAGE_READWRITE | 0x40)):
                pages.append({'BaseAddress': mbi.BaseAddress, 'RegionSize': mbi.RegionSize})
            address = mbi.BaseAddress + mbi.RegionSize
        return pages

    def toggle_collector(self):
        self.is_active = not self.is_active
        if self.is_active:
            print("[*] F9 Pressed: Starting Discovery Mode.")
            self.msg_label.config(text="SEARCHING HP...", fg="orange")
            self.root.update() # Force UI Update immediately
            self.target_address = None
            Thread(target=self.main_loop, daemon=True).start()
        else:
            print("[*] F9 Pressed: Stopping Smart Collector.")
            self.msg_label.config(text="READY", fg="lime")
            self.status_label.config(text="[F9] START COLLECTING", fg="white")
            self.root.update()

    def main_loop(self):
        if not self.attach(): return
        
        # 1. Reset & First Scan (Snapshot)
        self.potential_addresses = []
        self.last_values = {}
        pages = self.get_memory_pages()
        for page in pages:
            try:
                data = self.pm.read_bytes(page['BaseAddress'], page['RegionSize'])
                for j in range(0, len(data) - 3, 4):
                    addr = page['BaseAddress'] + j
                    val = struct.unpack('<I', data[j:j+4])[0]
                    # Targeted Range: 50 to 5000 (Fits normal monsters like Imps/Wolves)
                    if 50 <= val <= 5000: 
                        self.potential_addresses.append(addr)
                        self.last_values[addr] = val
            except: continue
        
        print(f"[*] Discovery Phase: {len(self.potential_addresses)} candidates.")
        
        sct = mss.mss()
        
        # 2. Refine & Capture Loop
        while self.is_active:
            if self.target_address is None:
                # Still searching for the HP address
                refined = []
                for addr in self.potential_addresses:
                    try:
                        curr = self.pm.read_int(addr)
                        last = self.last_values.get(addr, 0)
                        if 1 < curr < last: # Decreased
                            refined.append(addr)
                        self.last_values[addr] = curr
                    except: continue
                
                self.potential_addresses = refined
                # Blinking Heartbeat in UI
                self.heartbeat = not self.heartbeat
                hb_icon = "●" if self.heartbeat else "○"
                self.count_label.config(text=f"{hb_icon} Searching... ({len(self.potential_addresses)})")
                
                if 0 < len(self.potential_addresses) <= 5:
                    # Loosened condition: Lock onto the first candidate if pool is small
                    self.target_address = self.potential_addresses[0]
                    print(f"[!] HP ADDRESS LOCKED-ON (Pool size: {len(self.potential_addresses)}): {hex(self.target_address)}")
                    self.msg_label.config(text="COLLECTING DATA!", fg="gold")
                    self.count_label.config(text=f"Locked: {hex(self.target_address)}")
                elif len(self.potential_addresses) == 0:
                    # Auto-restart if all candidates lost
                    print("[!] All candidates lost. Restarting Search.")
                    self.toggle_collector() # Turn off
                    time.sleep(1)
                    self.toggle_collector() # Turn back on
                    break
            else:
                # HP Address identified, start capturing
                try:
                    curr_hp = self.pm.read_int(self.target_address)
                    last_hp = self.last_values.get(self.target_address, 0)
                    
                    if 0 < curr_hp < last_hp:
                        # HP Dropped! Capture Image
                        mx, my = pydirectinput.position()
                        
                        # Diagnostic: Save full screen on first hit
                        if self.first_capture:
                            debug_file = f"{self.save_dir}/DEBUG_FULLSCREEN.png"
                            sct.shot(output=debug_file)
                            print(f"[*] DIAGNOSTIC: Full-screen saved to {debug_file}")
                            print(f"[*] INFO: Mouse detected at ({mx}, {my})")
                            self.first_capture = False

                        monitor = {
                            "top": my - self.crop_size // 2,
                            "left": mx - self.crop_size // 2,
                            "width": self.crop_size,
                            "height": self.crop_size
                        }
                        
                        filename = f"{self.save_dir}/monster_{int(time.time())}_{uuid.uuid4().hex[:4]}.png"
                        sct_img = sct.grab(monitor)
                        mss.tools.to_png(sct_img.rgb, sct_img.size, output=filename)
                        print(f"[{time.strftime('%H:%M:%S')}] [SAVED] at ({mx}, {my}) -> {os.path.basename(filename)}")
                        self.last_values[self.target_address] = curr_hp
                    
                    elif curr_hp > last_hp:
                        # Probably targeted a new monster (HP reset)
                        self.last_values[self.target_address] = curr_hp
                        
                except Exception as e:
                    print(f"[-] Capture Error: {e}")
                    self.target_address = None # Reset discovery if lost
            
            time.sleep(0.5)

    def run(self):
        if not os.path.exists(self.save_dir): os.makedirs(self.save_dir)
        keyboard.add_hotkey('f9', self.toggle_collector)
        print("[*] Smart Collector HUD Active. Press F9 to target and hunt.")
        self.root.mainloop()

if __name__ == "__main__":
    collector = SmartCollector()
    collector.run()
