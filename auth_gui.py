import customtkinter as ctk
import tkinter.messagebox as messagebox
from auth import AuthManager, LicenseExpiredError
import sys
import time
import logging
from PIL import Image
import os
import config

# Configure Appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

logger = logging.getLogger(__name__)

class AuthWindow(ctk.CTk):
    def __init__(self, is_pro=True):
        super().__init__()

        self.is_pro = is_pro
        self.title(f"[{config.BRAND_NAME_KR}] NPlace-DB 시작하기")
        self.geometry("480x560")
        self.resizable(False, False)
        
        # CI/BI Colors
        self.brand_deep_blue = config.COLOR_DEEP_BLUE
        self.brand_purple = config.COLOR_ELECTRIC_PURPLE
        self.brand_green = config.COLOR_NEON_GREEN
        self.bg_dark = config.COLOR_DARK_BG
        self.card_navy = "#151934"
        self.text_white = "#FFFFFF"
        self.text_muted = "#94A3B8"
        
        self.configure(fg_color=self.bg_dark)

        # 1. Header Section
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(pady=(30, 10), padx=30, fill="x")

        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'MarketingMonster_logo.png')
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                self.logo_image = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 80))
                self.logo_label = ctk.CTkLabel(self.header_frame, image=self.logo_image, text="")
                self.logo_label.pack(pady=(0, 5))
            except Exception as e:
                logger.error(f"Logo load error: {e}")

        self.label_title = ctk.CTkLabel(self.header_frame, text="NPlace-DB", 
                                        font=("Arial", 36, "bold"), text_color=self.brand_green)
        self.label_title.pack()

        # 2. Main Container (Stage-based)
        self.main_card = ctk.CTkFrame(self, fg_color=self.card_navy, corner_radius=24, 
                                      border_width=1, border_color="#2D3748")
        self.main_card.pack(pady=(10, 0), padx=35, fill="both", expand=True)

        self.hwid = AuthManager.get_hwid()
        self.authenticated = False

        # --- Stage 1: Welcome/Trial Stage ---
        self.welcome_stage = ctk.CTkFrame(self.main_card, fg_color="transparent")
        self.welcome_stage.pack(fill="both", expand=True, padx=20, pady=20)

        self.lbl_welcome = ctk.CTkLabel(self.welcome_stage, text="환영합니다!", 
                                       font=("Arial", 22, "bold"), text_color=self.text_white)
        self.lbl_welcome.pack(pady=(10, 10))

        self.lbl_trial_desc = ctk.CTkLabel(self.welcome_stage, 
                                           text="NPlace-DB의 강력한 기능을\n지금 바로 무료로 체험해보세요.\n\n[생애 단 1회, 총 50건 제공]", 
                                           font=("Arial", 16, "bold"), text_color=self.brand_green, justify="center")
        self.lbl_trial_desc.pack(pady=(0, 25))

        self.btn_start_trial = ctk.CTkButton(self.welcome_stage, text="1회 한정 50건 체험하기", 
                                            font=("Arial", 18, "bold"),
                                            fg_color=self.brand_purple, hover_color="#5300ce",
                                            height=70, corner_radius=20, command=self.start_trial_flow)
        self.btn_start_trial.pack(pady=(0, 20), fill="x", padx=10)

        self.btn_goto_auth = ctk.CTkButton(self.welcome_stage, text="이미 정품 키가 있습니다 (등록)", 
                                          font=("Arial", 12, "underline"),
                                          fg_color="transparent", text_color=self.text_muted,
                                          hover_color=self.bg_dark,
                                          height=30, command=self.show_auth_stage)
        self.btn_goto_auth.pack(side="bottom", pady=10)

        # --- Stage 2: Auth Stage (Hidden by default) ---
        self.auth_stage = ctk.CTkFrame(self.main_card, fg_color="transparent")
        # Hidden initially
        
        self.lbl_auth_title = ctk.CTkLabel(self.auth_stage, text="정품 라이선스 인증", 
                                          font=("Arial", 20, "bold"), text_color=self.brand_green)
        self.lbl_auth_title.pack(pady=(20, 10))

        self.entry_key = ctk.CTkEntry(self.auth_stage, placeholder_text="CM-XXXX-XXXX-XXXX", 
                                     height=58, font=("Arial", 18, "bold"), justify="center",
                                     fg_color="#0F172A", border_color="#334155",
                                     text_color=self.text_white, corner_radius=16)
        self.entry_key.pack(padx=15, fill="x", pady=10)

        self.btn_auth_submit = ctk.CTkButton(self.auth_stage, text="인증 및 활성화", 
                                            font=("Arial", 16, "bold"),
                                            fg_color=self.brand_purple, hover_color="#5300ce",
                                            height=55, corner_radius=16, command=self.authenticate)
        self.btn_auth_submit.pack(pady=(15, 10), padx=15, fill="x")

        self.btn_back_to_welcome = ctk.CTkButton(self.auth_stage, text="이전으로", 
                                               font=("Arial", 12),
                                               fg_color="transparent", text_color=self.text_muted,
                                               command=self.show_welcome_stage)
        self.btn_back_to_welcome.pack(pady=5)

        self.status_label = ctk.CTkLabel(self.main_card, text="", 
                                        font=("Arial", 12, "bold"), text_color="#F59E0B")
        self.status_label.pack(side="bottom", pady=15)

        # Check initial license status silently
        self.check_initial_status()

    def show_auth_stage(self):
        self.welcome_stage.pack_forget()
        self.auth_stage.pack(fill="both", expand=True, padx=20, pady=20)
        self.status_label.configure(text="시리얼 번호를 입력하세요.", text_color=self.text_muted)

    def show_welcome_stage(self):
        self.auth_stage.pack_forget()
        self.welcome_stage.pack(fill="both", expand=True, padx=20, pady=20)
        self.status_label.configure(text="")

    def check_initial_status(self):
        import threading
        def check():
            try:
                if AuthManager.check_license_status():
                    self.authenticated = True
                    self.after(0, self.destroy)
                else:
                    # [NEW] 체험판 가능 여부 체크
                    if not AuthManager.is_trial_available():
                        logger.info("🚫 체험판 한도 소진. 인증 화면으로 자동 전환합니다.")
                        self.after(0, self.show_auth_stage)
                        self.after(0, lambda: self.status_label.configure(
                            text="체험 한도(50건) 소진. 정품 인증이 필요합니다.", 
                            text_color="#EF4444"
                        ))
            except Exception as e:
                logger.error(f"Initial check error: {e}")
                
        t = threading.Thread(target=check, daemon=True)
        t.start()

    def start_trial_flow(self):
        self.status_label.configure(text="⏳ 체험판 초기화 중...", text_color=self.brand_green)
        self.update()
        success, msg = AuthManager.start_trial()
        if success:
            logger.info("Starting trial session...")
            # [FIX] Tell the dashboard process that we are in trial mode
            os.environ["NPLACE_TRIAL_MODE"] = "1"
            self.authenticated = True
            self.destroy()
        else:
            messagebox.showerror("체험판 시작 실패", msg)

    def authenticate(self):
        product_key = self.entry_key.get().strip()
        if not product_key:
            messagebox.showwarning("알림", "시리얼 번호를 입력해 주세요.")
            return

        self.status_label.configure(text="⏳ 서버 확인 중...", text_color="#3182CE")
        self.update()
        
        try:
            success, msg = AuthManager.validate_and_bind_key(product_key)
            if success:
                self.status_label.configure(text="✅ 인증 성공!", text_color=self.brand_green)
                self.update()
                time.sleep(1.0)
                self.authenticated = True
                self.destroy()
            else:
                self.status_label.configure(text=msg, text_color="#EF4444")
                messagebox.showerror("인증 실패", msg)
        except Exception as e:
            logger.error(f"Auth error: {e}")
            self.status_label.configure(text=f"오류: {e}", text_color="#EF4444")

def run_auth_flow(is_pro=True):
    try:
        app = AuthWindow(is_pro=is_pro)
        app.mainloop()
        return app.authenticated
    except Exception as e:
        logger.error(f"Error in run_auth_flow: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    run_auth_flow()
