import customtkinter as ctk
import tkinter.messagebox as messagebox
import threading
import subprocess
import sys
import os
import time
from auth import AuthManager
from auth_gui import run_auth_flow
from crawler.local_db_handler import LocalDBHandler
from updater import MonsterUpdater
import config
import logging
from PIL import Image

# Configure logging to file for debugging
logging.basicConfig(
    filename=os.path.join(config.LOCAL_LOG_PATH, "app_debug.log"),
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger(__name__)

# [가이드 준수] Premium Dark Mode Configuration
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # [가이드 준수] Title & Branding
        self.title(f"[{config.BRAND_NAME_KR}] {config.SERVICE_NAME_KR} V1.0")
        self.geometry("900x700")
        self.configure(fg_color=config.COLOR_DARK_BG)
        
        # UI Styles
        self.accent_purple = config.COLOR_ELECTRIC_PURPLE
        self.accent_green = config.COLOR_NEON_GREEN
        self.btn_corner = 12 # [가이드 준수] 12px 라운드 처리

        
        # UI Setup
        self.setup_ui()
        
        self.crawler_process = None
        self.is_running = False

        # [NEW] Check for Updates
        self.after(100, self.start_update_check)

        # [NEW] Test License Notification
        self.after(500, self.check_test_license_notification)

    def start_update_check(self):
        """배경 쓰레드에서 업데이트를 확인합니다."""
        thread = threading.Thread(target=self.run_update_flow, daemon=True)
        thread.start()

    def run_update_flow(self):
        try:
            update_info = MonsterUpdater.check_for_updates()
            if update_info:
                latest_v = update_info.get("version")
                # UI 쓰레드에서 팝업 표시
                self.after(0, lambda: self.show_update_dialog(update_info))
        except Exception as e:
            logger.error(f"Update flow error: {e}")

    def show_update_dialog(self, info):
        latest_v = info.get("version")
        note = info.get("release_notes", "새로운 버전이 출시되었습니다.")
        
        if messagebox.askyesno("업데이트 알림", 
                                f"새로운 버전({latest_v})이 발견되었습니다.\n\n"
                                f"내용: {note}\n\n"
                                f"지금 업데이트를 진행하시겠습니까?\n(확인을 누르면 자동 업데이트 후 재시작됩니다.)"):
            self.perform_update(info)

    def perform_update(self, info):
        # 모달 진행 표시 (간략하게 상태바 활용)
        self.label_status.configure(text="상태: 업데이트 다운로드 중...", text_color=self.accent_purple)
        self.btn_start.configure(state="disabled")
        
        def download_and_apply():
            url = info.get("download_url")
            temp_zip = "monster_update.zip"
            if MonsterUpdater.download_update(url, temp_zip):
                self.after(0, lambda: MonsterUpdater.apply_update_and_restart(temp_zip))
            else:
                self.after(0, lambda: messagebox.showerror("업데이트 실패", "다운로드 중 오류가 발생했습니다."))
                self.after(0, self.reset_ui)

        threading.Thread(target=download_and_apply, daemon=True).start()

    def check_test_license_notification(self):
        key = AuthManager.get_serial_key()
        logger.debug(f"Checking license notification. Key: {key}")
        
        if key == "TRIAL-MODE":
            logger.info("Trial mode detected! Displaying guidance popup.")
            messagebox.showinfo(
                "체험판 안내",
                "현재 체험판 모드로 실행 중입니다.\n\n"
                "• 체험판은 하루 최대 50건까지 수집이 가능합니다.\n"
                "• 수집된 데이터의 엑셀 저장 기능을 테스트해보실 수 있습니다.\n\n"
                "정식 버전 전환을 원하시면 관리자에게 문의해주세요."
            )
        elif key and (key.startswith('TEST-') or "-TEST-" in key):
            logger.info("Test license detected! Displaying guidance popup.")
            messagebox.showinfo(
                "테스트 라이선스 안내",
                "현재 테스트용 인증키로 접속되었습니다.\n\n"
                "• 이 인증키는 테스트용으로 최대 100개까지 수집이 가능합니다.\n"
                "• 사용 기간은 발급일로부터 1일(24시간) 동안 가능합니다.\n\n"
                "정식 버전 전환을 원하시면 관리자에게 문의해주세요."
            )

    def setup_ui(self):
        # Header
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(pady=(20, 10), padx=20, fill="x")

        # Load and display logo
        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'MarketingMonster_logo.png')
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                self.logo_image = ctk.CTkImage(light_image=img, dark_image=img, size=(60, 60))
                self.logo_label = ctk.CTkLabel(self.header_frame, image=self.logo_image, text="")
                self.logo_label.pack(pady=(0, 5))
            except Exception as e:
                logger.error(f"Logo load error: {e}")

        self.label_header = ctk.CTkLabel(self.header_frame, text=f"{config.BRAND_NAME_KR} {config.SERVICE_NAME_KR}", 
                                        font=("Arial", 28, "bold"), text_color=self.accent_green)
        self.label_header.pack()


        # Input Frame
        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.pack(pady=10, padx=20, fill="x")

        self.label_keyword = ctk.CTkLabel(self.input_frame, text="검색 키워드 (상호/업종 등):")
        self.label_keyword.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.entry_keyword = ctk.CTkEntry(self.input_frame, width=250, placeholder_text="예: 식당, 미용실, 피부샵 등")
        self.entry_keyword.grid(row=0, column=1, padx=10, pady=10)
        self.entry_keyword.insert(0, "") # 기본값 제거

        self.label_area = ctk.CTkLabel(self.input_frame, text="지역 (예: 서울 강남구):")
        self.label_area.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        self.entry_area = ctk.CTkEntry(self.input_frame, width=250, placeholder_text="예: 서울 강남구,인천,경기 부천시")

        self.entry_area.grid(row=1, column=1, padx=10, pady=10)
        self.entry_area.insert(0, "") # 기본값 제거

        self.label_exclude = ctk.CTkLabel(self.input_frame, text="제외 키워드 (콤마로 구분):")
        self.label_exclude.grid(row=2, column=0, padx=10, pady=10, sticky="w")

        self.entry_exclude = ctk.CTkEntry(self.input_frame, width=250, placeholder_text="예: 태닝, 마사지, 왁싱")
        self.entry_exclude.grid(row=2, column=1, padx=10, pady=10)

        self.entry_count = ctk.CTkEntry(self.input_frame, width=100)
        self.entry_count.grid(row=3, column=1, padx=10, pady=10, sticky="w")
        self.entry_count.insert(0, "100")

        # [NEW] Filter Mode & Keyword
        self.label_filter_mode = ctk.CTkLabel(self.input_frame, text="2차 필터링 조건:")
        self.label_filter_mode.grid(row=4, column=0, padx=10, pady=10, sticky="w")

        self.option_filter_mode = ctk.CTkOptionMenu(self.input_frame, values=["전체(상호/업종/메뉴 포함)", "상호명 일치", "업종명 일치"], 
                                                  width=180, dynamic_resizing=False)
        self.option_filter_mode.grid(row=4, column=1, padx=10, pady=10, sticky="w")
        self.option_filter_mode.set("전체(상호/업종/메뉴 포함)")

        self.entry_filter_keyword = ctk.CTkEntry(self.input_frame, width=150, placeholder_text="필터링 키워드")
        self.entry_filter_keyword.grid(row=4, column=1, padx=170, pady=10, sticky="w")

        # Progress Summary Frame
        self.summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_frame.pack(pady=5, padx=20, fill="x")

        # 4 Cards
        self.card_frame = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        self.card_frame.pack(fill="x", pady=2)
        self.card_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def create_card(parent, title, default_val, col):
            f = ctk.CTkFrame(parent, corner_radius=8, fg_color="#1E293B")
            f.grid(row=0, column=col, padx=4, sticky="ew")
            ctk.CTkLabel(f, text=title, font=("Arial", 11), text_color="#94A3B8").pack(pady=(5, 0))
            lbl = ctk.CTkLabel(f, text=default_val, font=("Arial", 16, "bold"), text_color=self.accent_green)
            lbl.pack(pady=(0, 5))
            return lbl

        self.lbl_target_m = create_card(self.card_frame, "예상 대상 수", "0 건", 0)
        self.lbl_current_n = create_card(self.card_frame, "현재 수집 개수", "0 건", 1)
        self.lbl_elapsed = create_card(self.card_frame, "총 소요시간", "0초", 2)
        self.lbl_eta = create_card(self.card_frame, "예상 남은 시간", "0초", 3)

        # Progress Bar & Text
        self.progress_info_frame = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        self.progress_info_frame.pack(fill="x", pady=(5, 2))
        
        self.lbl_progress_text = ctk.CTkLabel(self.progress_info_frame, text="전체 완료율: 0 / 0 (0.0%)", font=("Arial", 12, "bold"))
        self.lbl_progress_text.pack(side="left")
        
        self.lbl_progress_subtext = ctk.CTkLabel(self.progress_info_frame, text="대기 중", font=("Arial", 11), text_color="#94A3B8")
        self.lbl_progress_subtext.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(self.summary_frame, height=12, progress_color=self.accent_green)
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_bar.set(0.0)

        # Status Label
        self.label_status = ctk.CTkLabel(self, text="상태: 대기 중", font=("Arial", 12), text_color="#94A3B8")
        self.label_status.pack(pady=2)

        # Control Buttons
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(pady=20)

        self.btn_start = ctk.CTkButton(self.button_frame, text="수집 시작", 
                                      fg_color=self.accent_purple, hover_color="#5300ce", 
                                      corner_radius=self.btn_corner, font=("Arial", 13, "bold"),
                                      command=self.start_crawling)
        self.btn_start.grid(row=0, column=0, padx=10)

        self.btn_stop = ctk.CTkButton(self.button_frame, text="중지", 
                                     fg_color="#EF4444", hover_color="#DC2626", 
                                     corner_radius=self.btn_corner, font=("Arial", 13, "bold"),
                                     command=self.stop_crawling, state="disabled")
        self.btn_stop.grid(row=0, column=1, padx=10)

        self.btn_export = ctk.CTkButton(self.button_frame, text="엑셀 저장", 
                                       fg_color="#334155", corner_radius=self.btn_corner, 
                                       font=("Arial", 13, "bold"),
                                       command=self.export_to_excel)
        self.btn_export.grid(row=0, column=2, padx=10)

        self.btn_refresh = ctk.CTkButton(self.button_frame, text="새로고침", 
                                        fg_color="#334155", corner_radius=self.btn_corner, 
                                        font=("Arial", 13, "bold"),
                                        command=self.refresh_table)
        self.btn_refresh.grid(row=0, column=3, padx=10)


        # Tabs for Logs and Data
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.tab_log = self.tabview.add("작업 로그")
        self.tab_data = self.tabview.add("수집 데이터")

        # Log Text Area
        self.log_text = ctk.CTkTextbox(self.tab_log)
        self.log_text.pack(pady=10, padx=10, fill="both", expand=True)
        self.log_text.configure(state="disabled")

        # Data Table Area (Simple Placeholder or Scrollable Frame)
        self.data_container = ctk.CTkScrollableFrame(self.tab_data)
        self.data_container.pack(pady=10, padx=10, fill="both", expand=True)
        self.refresh_table()

    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def start_crawling(self):
        if self.is_running: return
        
        keyword = self.entry_keyword.get().strip()
        area = self.entry_area.get().strip()
        count = self.entry_count.get().strip()
        exclude = self.entry_exclude.get().strip()

        if not keyword or not area:
            messagebox.showwarning("경고", "키워드와 지역을 입력해주세요.")
            return

        # [NEW] Strict License Status Check before starting
        if not AuthManager.check_license_status():
            messagebox.showerror("라이선스 오류", "라이선스가 만료되었거나 유효하지 않습니다.\n프로그램을 다시 실행하여 인증해 주세요.")
            self.destroy() # Close the app if license is invalid
            return

        # [NEW] Enforce Collection Limit (Lifetime)
        limit = AuthManager.get_collection_limit()
        serial = AuthManager.get_serial_key()
        
        try:
            requested_count = int(count) if count else 0
        except ValueError:
            requested_count = 0

        if limit:
            from crawler.local_db_handler import LocalDBHandler
            db = LocalDBHandler()
            current_total = db.get_count()
            
            # 체험판 모드인 경우 누적 수집량을 체크 (Monster Rule 1.3 - Lifetime Limit)
            if serial == "TRIAL-MODE":
                remaining = max(0, limit - current_total)
                if remaining <= 0:
                    messagebox.showerror("체험 한도 초과", "무료 체험판 수집 한도(50건)를 모두 소진하셨습니다.\n정식 라이선스를 구매하여 이용해 주세요.")
                    self.btn_start.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    self.is_running = False
                    return
                
                if requested_count > remaining:
                    messagebox.showinfo("체험 한도 안내", f"남은 체험 수집 가능 수량은 {remaining}건입니다.\n수집 목표가 {remaining}건으로 자동 조정되었습니다.")
                    requested_count = remaining
                    count = str(remaining)
                    self.entry_count.delete(0, "end")
                    self.entry_count.insert(0, count)
            
            # 테스트 키 등 일반적인 단일 세션 제한 (기존 로직 유지)
            elif requested_count > limit:
                messagebox.showinfo("라이선스 제한", f"현재 사용 중인 라이선스는 회당 최대 {limit}건까지만 수집 가능합니다.\n수집 목표가 {limit}건으로 자동 조정되었습니다.")
                count = str(limit)
                self.entry_count.delete(0, "end")
                self.entry_count.insert(0, count)

        self.is_running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.label_status.configure(text="상태: 크롤링 중...")
        
        limit_str = f" (제한: {limit}건)" if limit else ""
        self.log(f"🚀 작업 시작: {area} {keyword} ({count}건 목표){limit_str}")

        # Run in separate thread
        filter_mode_map = {"전체(상호/업종/메뉴 포함)": "all", "상호명 일치": "name", "업종명 일치": "category"}
        f_mode = filter_mode_map.get(self.option_filter_mode.get(), "all")
        f_keyword = self.entry_filter_keyword.get().strip()

        thread = threading.Thread(target=self.run_crawler_process, args=(area, count, keyword, exclude, f_mode, f_keyword), daemon=True)
        thread.start()

    def run_crawler_process(self, area, count, shop_type, exclude="", filter_mode="all", filter_keyword=""):
        try:
            # We use the existing script logic but could also import it.
            # Running as a subprocess keeps the GUI more isolated and safer for processes like browser close.
            cmd = [sys.executable, "step1_refined_crawler.py", area, count, shop_type]
            if exclude:
                cmd.extend(["--exclude", exclude])
            if filter_mode != "all":
                cmd.extend(["--filter-mode", filter_mode, "--filter-keyword", filter_keyword])
            # Since we modified the script to take shop_type via run_crawler, 
            # we need to make sure the CLI args are handled or use a temporary settings file.
            
            # For simplicity, let's create a temporary settings file that the crawler reads
            import json
            SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crawler_settings.json')
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
            
            settings["shop_type"] = shop_type
            settings["app_mode"] = True
            
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)

            self.crawler_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                encoding="utf-8"
            )

            error_captured = None
            for line in iter(self.crawler_process.stdout.readline, ""):
                if not self.is_running:
                    self.crawler_process.terminate()
                    break
                
                cleaned_line = line.strip()
                self.log(cleaned_line)
                
                # [가이드 준수] 실시간 에러 감지 및 모달 알림
                if "CRITICAL ERROR:" in cleaned_line:
                    error_msg = cleaned_line.split("CRITICAL ERROR:")[-1].strip()
                    error_captured = error_msg
                    # UI Thread에서 모달창 즉시 실행
                    self.after(0, lambda msg=error_msg: messagebox.showerror("크롤링 중단됨", f"엔진에서 치명적 오류가 발생했습니다:\n\n{msg}"))
                # [가이드 준수] 실시간 진행 요약 (PROGRESS_JSON) 및 로그 필터링
                if "PROGRESS_JSON:" in cleaned_line:
                    try:
                        import json
                        json_str = cleaned_line.split("PROGRESS_JSON:")[-1].strip()
                        data = json.loads(json_str)
                        self.after(0, self.update_progress_ui, data)
                    except Exception as e:
                        logger.error(f"Failed to parse PROGRESS_JSON: {e}")
                elif "Progress:" in cleaned_line:
                    # Fallback legacy progress
                    self.after(0, lambda text=cleaned_line: self.label_status.configure(text=f"상태: {text}"))
                elif "✅ Saved (" in cleaned_line:
                    # Ignore real-time item collection log to clean up output
                    pass
                else:
                    self.after(0, self.log, cleaned_line)

            exit_code = self.crawler_process.wait()
            
            if exit_code != 0 and not error_captured:
                # 에러 메시지를 명시적으로 잡지 못했지만 비정상 종료된 경우
                self.after(0, lambda: messagebox.showerror("시스템 오류", "크롤러 엔진이 예기치 않게 종료되었습니다.\n로그를 확인해 주세요."))
                self.log(f"❌ 엔진 비정상 종료 (Exit Code: {exit_code})")
            elif exit_code == 0:
                self.log("✅ 모든 작업이 성공적으로 종료되었습니다.")

        except Exception as e:
            self.log(f"❌ 오류 발생: {e}")
        finally:
            self.is_running = False
            self.after(0, self.reset_ui)

    def reset_ui(self):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.label_status.configure(text="상태: 완료")
        
    def update_progress_ui(self, data):
        n = data.get("success_count", 0)
        m = data.get("estimated_total", 0)
        elapsed = data.get("elapsed_sec", 0)
        eta = data.get("eta_sec", 0)
        ratio = data.get("completion_ratio", 0)
        avg_sec = data.get("avg_sec_per_item", 0)
        segment = data.get("current_segment", "")
        
        def format_time(seconds):
            if seconds < 60: return f"{seconds}초"
            mins, s = divmod(seconds, 60)
            if mins < 60: return f"{mins}분 {s}초"
            h, mins = divmod(mins, 60)
            return f"{h}시간 {mins}분"
            
        self.lbl_target_m.configure(text=f"{m} 건")
        self.lbl_current_n.configure(text=f"{n} 건")
        self.lbl_elapsed.configure(text=format_time(elapsed))
        self.lbl_eta.configure(text=format_time(eta))
        
        display_ratio = ratio * 100
        self.lbl_progress_text.configure(text=f"전체 완료율: {n} / {m} ({display_ratio:.1f}%)")
        self.lbl_progress_subtext.configure(text=f"개당 {avg_sec}초 | 타겟: {segment}")
        
        bar_width = max(ratio, 0.012) # min 1.2% visible
        self.progress_bar.set(bar_width)

    def stop_crawling(self):
        if not self.is_running: return
        self.is_running = False
        self.log("🛑 중지 요청 중...")
        if self.crawler_process:
            self.crawler_process.terminate()
        self.label_status.configure(text="상태: 중지됨")

    def export_to_excel(self):
        self.log("📊 엑셀 내보내기 시작...")
        try:
            from exporter import export_to_xlsx
            file_path = export_to_xlsx()
            if file_path:
                messagebox.showinfo("완료", f"엑셀 파일이 저장되었습니다:\n{file_path}")
                self.log(f"✅ 엑셀 저장 완료: {file_path}")
            else:
                messagebox.showerror("오류", "데이터가 없거나 저장 중 오류가 발생했습니다.")
        except Exception as e:
            self.log(f"❌ 엑셀 내보내기 실패: {e}")

    def refresh_table(self):
        """Refreshes the data preview table from SQLite."""
        for widget in self.data_container.winfo_children():
            widget.destroy()
            
        try:
            db_local = LocalDBHandler(config.LOCAL_DB_PATH)
            shops = db_local.get_all_shops()
            
            if not shops:
                ctk.CTkLabel(self.data_container, text="수집된 데이터가 없습니다.").pack(pady=20)
                return

            for shop in shops[:50]: # Limit to 50 for performance
                frame = ctk.CTkFrame(self.data_container)
                frame.pack(fill="x", pady=2, padx=5)
                
                name = shop.get("name", "N/A")
                phone = shop.get("phone", "N/A")
                area = shop.get("address", "N/A")
                
                ctk.CTkLabel(frame, text=f"{name} | {phone} | {area}", font=("Arial", 11), anchor="w").pack(side="left", padx=10)
        except Exception as e:
            logger.error(f"Error refreshing table: {e}")

        except Exception as e:
            logger.error(f"Error refreshing table: {e}")

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    
    # [FIX] Intercept arguments for PyInstaller packaged executable
    if len(sys.argv) > 1:
        # For frozen apps, ensure _internal (sys._MEIPASS) is in sys.path
        if getattr(sys, 'frozen', False):
            internal_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            if internal_path not in sys.path:
                sys.path.insert(0, internal_path)
            
            # Explicitly add _internal as sometimes it's nested
            alt_internal = os.path.join(os.path.dirname(sys.executable), "_internal")
            if os.path.exists(alt_internal) and alt_internal not in sys.path:
                sys.path.insert(0, alt_internal)

        if sys.argv[1] == "-m":
            if len(sys.argv) > 2 and sys.argv[2] == "streamlit":
                import streamlit.web.cli as stcli
                sys.argv = ["streamlit"] + sys.argv[3:]
                sys.exit(stcli.main())
            elif len(sys.argv) > 2 and sys.argv[2] == "playwright":
                sys.argv = ["playwright"] + sys.argv[3:]
                import runpy
                try:
                    runpy.run_module("playwright.__main__", run_name="__main__")
                except SystemExit as e:
                    sys.exit(e.code)
                sys.exit(0)
            sys.exit(0)
        elif sys.argv[1] == "-c":
            if len(sys.argv) > 2:
                exec(sys.argv[2])
            sys.exit(0)
        elif "step1_" in sys.argv[1] or "engine_recover_missing" in sys.argv[1]:
            # e.g., "step1_refined_crawler.py"
            import os
            import runpy
            arg1 = sys.argv[1]
            base_name = os.path.basename(arg1)
            
            # Find the actual file path
            script_path = None
            if os.path.exists(arg1):
                script_path = arg1
            elif getattr(sys, 'frozen', False):
                # Search in _MEIPASS or _internal
                search_dirs = [getattr(sys, '_MEIPASS', ''), os.path.join(os.path.dirname(sys.executable), "_internal")]
                for d in search_dirs:
                    cand = os.path.join(d, base_name)
                    if os.path.exists(cand):
                        script_path = cand
                        break
            
            if script_path:
                logger.info(f"Running script via run_path: {script_path}")
                sys.argv = sys.argv[1:] # Shift args
                try:
                    runpy.run_path(script_path, run_name="__main__")
                except SystemExit as e:
                    sys.exit(e.code)
                except Exception as e:
                    logger.error(f"Error running {base_name}: {e}", exc_info=True)
                    sys.exit(1)
                sys.exit(0)
            else:
                logger.error(f"Could not find script: {base_name}")
                sys.exit(1)
        else:
            # Any unmatched argument exits immediately to prevent GUI fork bombs
            sys.exit(0)

    logger.info("Application starting (Launcher Mode)...")
    try:
        # Check for data directory presence
        os.makedirs("data", exist_ok=True)
        
        # 1. HWID Authentication Flow
        if run_auth_flow(is_pro=True):
            logger.info("Authentication successful. Launching main dashboard launcher.")
            
            # Explicitly call our new launcher
            import main_launcher
            main_launcher.main() 
        else:
            logger.info("Authentication failed or cancelled.")
            sys.exit(0)
    except Exception as e:
        logger.critical(f"Critical startup crash: {e}", exc_info=True)
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("실행 오류", f"프로그램 시작 중 오류가 발생했습니다:\n{e}")
        sys.exit(1)
