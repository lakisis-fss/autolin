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
        
        # AOB ?ㅼ틦???섏씠釉뚮━???붿쭊 蹂??        # ?섏쨷??移섑듃?붿쭊?쇰줈 ?뺤떎???⑦꽩??李얠쑝?⑤떎硫???怨녹뿉 b"\x48\x8B\x05....\x48\x8B\x88" ?뺥깭濡?遺숈뿬?ｌ쑝?몄슂.
        # ?⑦꽩??鍮꾩뼱?덇굅???ㅼ틪???ㅽ뙣?섎㈃ fallback_offset???먮룞?쇰줈 ?ъ슜?⑸땲??
        self.char_base_pattern = b"" 
        self.fallback_offset = 0x149b350
        self.dynamic_char_offset = self.fallback_offset
        
        # ?숈쟻 罹먮┃???꾨줈???곗씠?곕쿋?댁뒪
        # 罹먮┃??援ъ“泥?蹂??媛먯????ㅽ봽???뺣낫
        self.profiles = {
            14: {
                "level_off": 0x1c,      # LEVEL ?ㅽ봽??                "exp_off": 0x28,        # EXP_Abs ?ㅽ봽??                "lvl1_entry": 0xb0,
                "lvl1_off": 0x28
            },
            11: {
                "level_off": 0x2b8,     # LEVEL ?ㅽ봽??                "exp_off": 0x2c4,       # EXP_Abs ?ㅽ봽??                "lvl1_entry": 0xb0,
                "lvl1_off": 0x28
            }
        }
        
        self.current_profile_lvl = 14
        self.last_attach_attempt = 0
        
        # ?섏씠釉뚮━??寃쏀뿕移?罹섎━釉뚮젅?댁뀡 ?뺣낫 (?ъ슜 以묐떒, ?뺤쟻 ?뚯씠釉??ъ슜)
        self.exp_max_table = {
            14: 7238687, # ?덈꺼 14??100% ?꾨떖 ?꾩슂 寃쏀뿕移?(??궛移?
            11: 1800000  # ?덈꺼 11 ?덉떆
        }
        
        # 媛諛?援ъ“泥?AOB 吏臾?(?ъ슜?먭? create_aob_helper.py 濡?異붿텧?섏뿬 ?ш린??遺숈뿬?ｌ쓬)
        self.struct_aob_pattern = b"\x1f\x00\x00\x00\xb0\xac\x00\x00\x16\x00\x0c\x00\x00\x00\x00\x00"
        
        # ?щ쭔??援ъ“泥??꾩슜 AOB 吏臾?(臾닿쾶? ?꾩쟾???ㅻⅨ ?숈뿉 議댁옱??
        self.struct_fd_aob_pattern = b"\x00\x00\x0c\x42\x00\x00\x84\x42\x00\x00\x00\x00\x10\xa3\x8e\xd0"
        
        # ?ㅼ떆媛?媛諛?臾닿쾶 諛??щ쭔???뺣룆???ㅽ봽??罹먯떆 (?깅뒫 理쒖쟻?붿슜)
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
            
            # ?꾨줈?몄뒪 ?곌껐 吏곹썑 AOB ?ㅼ틦???붿쭊 媛??(1?뚯꽦)
            self.find_dynamic_base_offset(module)
            
            return True
        except Exception:
            return False

    def find_dynamic_base_offset(self, module):
        """AOB ?ㅼ틦?앹쓣 ?듯빐 寃뚯엫 紐⑤뱢(.text)?먯꽌 罹먮┃??踰좎씠???ㅽ봽?뗭쓣 ?숈쟻?쇰줈 異붿텧?⑸땲??"""
        if not self.pm or not module:
            self.dynamic_char_offset = self.fallback_offset
            return

        # 1. ?ъ슜?먭? AOB ?⑦꽩???낅젰?섏? ?딆븯?ㅻ㈃ ?ㅼ틪??嫄대꼫?곌퀬 湲곗〈 ?ㅽ봽???ъ슜 (?덉쟾 紐⑤뱶)
        if not self.char_base_pattern:
            self.dynamic_char_offset = self.fallback_offset
            return

        try:
            print("[MemStateReader] AOB ?ㅼ틦??媛??以?..")
            found_addr = pymem.pattern.pattern_scan_module(self.pm.process_handle, module, self.char_base_pattern)
            
            if found_addr:
                # 64鍮꾪듃 RIP-relative 二쇱냼 怨꾩궛 濡쒖쭅 (紐낅졊??湲몄씠 7諛붿씠?? 蹂???쒖옉??3諛붿씠??媛??
                # ?ㅼ젣 李얠쑝???댁뀍釉붾━ ?⑦꽩 紐낅졊??援ъ“??留욊쾶 ??遺遺꾩쓣 誘몄꽭 議곗젙?댁빞 ?????덉뒿?덈떎.
                displacement = self.pm.read_int(found_addr + 3)
                absolute_address = found_addr + 7 + displacement
                new_offset = absolute_address - module.lpBaseOfDll
                self.dynamic_char_offset = new_offset
                print(f"[MemStateReader] AOB ?ㅼ틪 ?깃났! ?숈쟻 ?ㅽ봽???띾뱷: 0x{new_offset:x}")
            else:
                print("[MemStateReader] AOB ?ㅼ틪 ?ㅽ뙣: ?⑦꽩??李얠쓣 ???놁뒿?덈떎. ?덉쟾 紐⑤뱶濡?媛?숉빀?덈떎.")
                self.dynamic_char_offset = self.fallback_offset
        except Exception as e:
            print(f"[MemStateReader] AOB ?ㅼ틪 ?먮윭 ({e}). ?덉쟾 紐⑤뱶濡?媛?숉빀?덈떎.")
            self.dynamic_char_offset = self.fallback_offset

    def detect_character_profile(self):
        """罹먮┃??援ъ“泥??뺣낫瑜??ㅼ떆媛??먮룆?섏뿬 ?덈꺼 14 ?꾨줈?꾩씤吏 ?덈꺼 11 ?꾨줈?꾩씤吏 ?숈쟻 ?좊퀎"""
        if not self.pm:
            return
            
        try:
            char_base = self.base_address + self.dynamic_char_offset
            
            # 1. ?덈꺼 14 ?ㅽ봽??0x1c) 寃??(?꾩옱 ?ъ슜??罹먮┃?곗씤 ?덈꺼 14 理쒖슦???먮룆)
            val_14 = self.pm.read_int(char_base + 0x1c)
            if val_14 == 14:
                if self.current_profile_lvl != 14:
                    self.current_profile_lvl = 14
                    # ?꾨줈???꾪솚 ??湲곗〈 罹먯떆 媛뺤젣 臾댄슚?뷀븯???덈줈???몄뀡 罹먯떆 ?섎┰ ?좊룄
                    self.cached_offsets = {"lvl2_off": 0, "lvl3_wt_off": 0, "lvl3_fd_off": 0}
                    print(f"[MemStateReader] Profile auto-switched to Level 14 based on 0x1c detection.")
                return
                
            # 2. ?덈꺼 11 ?ㅽ봽??0x2b8) 寃??(?덈꺼 14媛 ?뺤떎???꾨땺 ?뚮쭔 ?덈꺼 11濡??덉쟾 ?꾪솚)
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
        """[DEPRECATED] ?뺤쟻 Max EXP ?뚯씠釉붿쓣 ?ъ슜?섎?濡????댁긽 ?몃?(OCR) 罹섎━釉뚮젅?댁뀡???섏〈?섏? ?딆뒿?덈떎."""
        pass

    def read_stealth_weight_food_via_tree_parser(self):
        """
        珥덇퀬???ㅼ떆媛?AOB ???ㅼ틦??(Global Heap AOB Scanner)
        ?댁젣 蹂듭옟???ъ씤??泥댁씤???吏 ?딄퀬, ???곸뿭??????踰??꾩닔議곗궗?섏뿬
        吏꾩쭨 臾닿쾶???덈? 二쇱냼瑜??곴뎄 罹먯떛?⑸땲??
        """
        if not self.pm:
            return 0, 0
            
        if not self.struct_aob_pattern or len(self.struct_aob_pattern) < 8:
            return 0, 0

        # --- 1. 珥덇퀬??罹먯떆 ?쎄린 (1000 FPS) ---
        if self.cached_abs_wt_addr > 0:
            try:
                weight = self.pm.read_int(self.cached_abs_wt_addr)
                food = 0.0
                if self.cached_abs_fd_addr > 0:
                    try:
                        food = self.pm.read_float(self.cached_abs_fd_addr)
                    except:
                        pass
                
                # ?좏슚??寃利?(臾닿쾶媛 0~100 ?ъ씠?멸??)
                if 0 <= weight <= 100:
                    return weight, food
                else:
                    # 臾댄슚?붾릺硫?罹먯떆 ??젣
                    self.cached_abs_wt_addr = 0
                    self.cached_abs_fd_addr = 0
            except Exception:
                self.cached_abs_wt_addr = 0
                self.cached_abs_fd_addr = 0

        # --- 2. ?꾩뿭 ??AOB ?ㅼ틦??(珥덇린 1?뚮쭔 諛쒖깮, ??0.5珥??뚯슂) ---
        print("[MemStateReader] ?좑툘 援ъ“泥??ㅽ봽???댄깉 媛먯?! ?꾩뿭 硫붾え由???AOB ?ㅼ틦???뚯엯 (理쒖큹 1?뚮쭔 諛쒖깮)...")
        
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
                    
                    # 臾닿쾶 AOB ?ㅼ틪
                    if self.cached_abs_wt_addr == 0 and wt_fixed_pattern:
                        idx_wt = data.find(wt_fixed_pattern)
                        if idx_wt != -1:
                            abs_wt_addr = addr + idx_wt - 4
                            w_val = self.pm.read_int(abs_wt_addr)
                            if 0 <= w_val <= 100:
                                self.cached_abs_wt_addr = abs_wt_addr
                                print(f"[MemStateReader] ??AOB 臾닿쾶 二쇱냼 ?ъ갑: {hex(abs_wt_addr)}")

                    # ?щ쭔??AOB ?ㅼ틪 (?낅┰??
                    if self.cached_abs_fd_addr == 0 and fd_fixed_pattern:
                        idx_fd = data.find(fd_fixed_pattern)
                        if idx_fd != -1:
                            abs_fd_addr = addr + idx_fd - 4
                            try:
                                f_val = self.pm.read_float(abs_fd_addr)
                                if 0.0 <= f_val <= 120.0:
                                    self.cached_abs_fd_addr = abs_fd_addr
                                    print(f"[MemStateReader] ??AOB ?щ쭔??二쇱냼 ?ъ갑: {hex(abs_fd_addr)}")
                            except Exception:
                                pass
                                
                    # ????李얠븯嫄곕굹, 李얠쓣 ???덈뒗 ?⑦꽩????李얠? 寃쎌슦 議곌린 醫낅즺
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
        [DEPRECATED] ?뺤쟻 ?ㅽ봽??濡ㅻ갚?쇰줈 ???댁긽 ?ъ슜?섏? ?딆뒿?덈떎.
        """
        return 0

    def get_state(self):
        if not self.pm:
            if not self.attach():
                return None

        try:
            # 0. 留??꾨젅?꾨쭏???꾩옱 罹먮┃???꾨줈???먮룞 ?좊퀎
            self.detect_character_profile()
            
            profile = self.profiles.get(self.current_profile_lvl)
            if not profile:
                return None
                
            char_base = self.base_address + self.dynamic_char_offset
            
            # 1. 泥대젰, 留덈굹, ?덈꺼, ?덈?寃쏀뿕移??띾뱷
            hp = self.pm.read_int(char_base + 0xc)
            max_hp = self.pm.read_int(char_base + 0x10)
            mp = self.pm.read_int(char_base + 0x14)
            max_mp = self.pm.read_int(char_base + 0x18)
            level = self.pm.read_int(char_base + profile["level_off"])
            
            # ?덈? 寃쏀뿕移섎? ?뺤쟻?쇰줈 吏곸젒 ?뺣룆 (?곹샇 李몄“ ?뚰듃 ?놁씠 ?쒖닔 硫붾え由??뺣룆)
            exp_abs = self.pm.read_int(char_base + profile["exp_off"])
            
            # 2. 珥덇퀬???ㅼ떆媛??몃━ ?댁꽍 ?뚯꽌瑜??듯빐 媛諛?臾닿쾶/?щ쭔媛??뺣룆 (?뚰듃 ?놁씠 ?ㅼ뒪濡??숈쟻 ??텛??
            weight, food = self.read_stealth_weight_food_via_tree_parser()
            
            # 3. ?ㅼ떆媛?醫뚰몴 諛?諛⑺뼢 ?대룆
            pos_x = self.pm.read_int(char_base + 0x0)
            pos_y = self.pm.read_int(char_base + 0x4)
            heading_val = self.pm.read_int(char_base + 0x8)
            
            # ?좏슚??寃??諛??뺤젣
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
            
            # 寃쏀뿕移?鍮꾩쑉 寃곗젙 (?쒖닔 硫붾え由??뺤쟻 Max EXP ?뚯씠釉??ъ슜)
            max_exp = self.exp_max_table.get(level, 0)
            if max_exp > 0:
                exp_pct = (exp_abs / float(max_exp)) * 100.0
            else:
                exp_pct = 0.0
                
            if exp_pct > 100.0: exp_pct = 99.9999
            exp_str = f"{exp_pct:.4f}%"
                
            # 諛⑺뼢 留ㅽ븨
            dir_map = {
                0: "遺?燧놅툘",
                1: "遺곷룞 ?쀯툘",
                2: "???∽툘",
                3: "?⑤룞 ?섓툘",
                4: "??燧뉛툘",
                5: "?⑥꽌 ?숋툘",
                6: "??燧낉툘",
                7: "遺곸꽌 ?뽳툘"
            }
            direction_str = dir_map.get(heading_val, "-")
            
            # ?ㅼ떆媛??먭?移섏쑀 ?뚯꽌 硫뷀??곗씠???붾쾭洹??뺣낫 ?섏쭛
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
