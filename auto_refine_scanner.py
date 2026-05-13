import pymem
import pymem.process
import keyboard
import time
import ctypes
import struct
import tkinter as tk
from threading import Thread, Lock

# Windows Constants
MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04

class AutoRefineScanner:
    def __init__(self, process_name="LC.exe"):
        self.process_name = process_name
        self.pm = None
        self.potential_addresses = []
        self.last_values = {}
        self.is_scanning = False
        self.lock = Lock()
        
        # Overlay UI
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.config(bg="black")
        self.root.geometry("250x200+10+10") # Taller for buttons
        self.root.lift()
        
        self.status_label = tk.Label(self.root, text="Status: READY", fg="white", bg="black", font=("Arial", 10, "bold"))
        self.status_label.pack(anchor="w")
        
        self.count_label = tk.Label(self.root, text="Matches: 0", fg="lime", bg="black", font=("Arial", 12, "bold"))
        self.count_label.pack(anchor="w")

        # Command Buttons for Manual Control (since hotkeys might be blocked)
        btn_frame = tk.Frame(self.root, bg="black")
        btn_frame.pack(anchor="w", pady=5)
        
        self.reset_btn = tk.Button(btn_frame, text="[ RESET ]", command=self.reset_scan, bg="#444", fg="white", activebackground="red", font=("Arial", 9, "bold"))
        self.reset_btn.pack(side="left", padx=5)
        
        self.track_btn = tk.Button(btn_frame, text="[ TRACK ]", command=self.toggle_auto_refine, bg="#444", fg="white", activebackground="orange", font=("Arial", 9, "bold"))
        self.track_btn.pack(side="left", padx=5)
        
        self.result_label = tk.Label(self.root, text="", fg="gold", bg="black", font=("Arial", 9), justify="left")
        self.result_label.pack(anchor="w")

    def attach(self):
        try:
            self.pm = pymem.Pymem(self.process_name)
            print(f"[*] Attached to {self.process_name}")
            return True
        except:
            self.status_label.config(text="Status: ERROR (Attach failed)", fg="red")
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

    def reset_scan(self):
        # Hotkey Detection Feedback (Flash RED)
        self.status_label.config(text="[HOTKEY F8] RESETTING...", fg="red")
        self.root.update()
        time.sleep(0.1)
        
        self.is_scanning = False
        self.status_label.config(text="Status: INITIALIZING...", fg="yellow")
        self.root.update()
        
        self.potential_addresses = []
        self.last_values = {}
        pages = self.get_memory_pages()
        for page in pages:
            try:
                data = self.pm.read_bytes(page['BaseAddress'], page['RegionSize'])
                for j in range(0, len(data) - 3, 4):
                    addr = page['BaseAddress'] + j
                    val = struct.unpack('<I', data[j:j+4])[0]
                    if 0 < val < 100000: # Filter for realistic HP values
                        self.potential_addresses.append(addr)
                        self.last_values[addr] = val
            except: continue
            
        self.count_label.config(text=f"Matches: {len(self.potential_addresses)}")
        self.status_label.config(text="Status: READY (Press F9 to Track)", fg="lime")
        print(f"[*] F8 Pressed: Initial snapshot complete ({len(self.potential_addresses)} addresses).")

    def toggle_auto_refine(self):
        self.is_scanning = not self.is_scanning
        if self.is_scanning:
            print("[*] F9 Pressed: Auto-Refining STARTED.")
            self.status_label.config(text="Status: AUTO-TRACKING (ON)", fg="orange")
            Thread(target=self.refine_loop, daemon=True).start()
        else:
            print("[*] F9 Pressed: Auto-Refining PAUSED.")
            self.status_label.config(text="Status: PAUSED", fg="white")

    def refine_loop(self):
        print("[*] Scan loop started.")
        while self.is_scanning:
            with self.lock:
                if not self.potential_addresses: 
                    print("[!] No addresses remaining. Stopping scan.")
                    self.is_scanning = False
                    break
                
                refined = []
                new_last_values = {}
                for addr in self.potential_addresses:
                    try:
                        curr = self.pm.read_int(addr)
                        last = self.last_values.get(addr, 0)
                        if 0 < curr < last: # Only keep if decreased
                            refined.append(addr)
                            new_last_values[addr] = curr
                        else:
                            new_last_values[addr] = curr # Keep value updated for future decreases
                    except: continue
                    
                self.potential_addresses = refined
                self.last_values.update(new_last_values)
            
            # Update UI (Outside Lock)
            self.count_label.config(text=f"Matches: {len(self.potential_addresses)}")
            print(f"[*] Heartbeat: Scanning {len(self.potential_addresses)} candidates...")
            
            if len(self.potential_addresses) <= 5:
                res_txt = "\n".join([f"{hex(a)}: {self.last_values[a]}" for a in self.potential_addresses])
                self.result_label.config(text=res_txt)
                # Log to file
                with open("detected_offsets.txt", "w") as f:
                    f.write(f"Matches at {time.ctime()}:\n" + res_txt)
            
            time.sleep(1.5) # Polling interval
        print("[*] Scan loop paused/stopped.")

    def run(self):
        if not self.attach(): return
        
        # Setup Hotkeys
        keyboard.add_hotkey('f8', self.reset_scan)
        keyboard.add_hotkey('f9', self.toggle_auto_refine)
        
        print("[*] Overlay running. Press F8 in-game to reset, F9 to track decreasing values.")
        self.root.mainloop()

if __name__ == "__main__":
    scanner = AutoRefineScanner("LC.exe")
    scanner.run()
