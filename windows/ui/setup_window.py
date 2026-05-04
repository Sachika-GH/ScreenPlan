"""Setup window - tkinter-based login/register UI for Windows, matching web panel design."""

import tkinter as tk
from tkinter import ttk
import webbrowser
import os


class SetupWindow:
    """Styled login window for first-time setup."""

    def __init__(self, on_success):
        self.on_success = on_success
        self._build()

    def _build(self):
        self.root = tk.Tk()
        self.root.title("ScreenPlan - Setup")
        self.root.geometry("400x520")
        self.root.configure(bg="#f4f6f9")
        self.root.resizable(False, False)

        BG = "#f4f6f9"
        BRAND = "#2563EB"
        BRAND_HOVER = "#1E3A5F"
        TEXT = "#111827"
        TEXT_SEC = "#4b5563"
        BORDER = "#e5e7eb"

        main = tk.Frame(self.root, bg=BG, padx=32, pady=32)
        main.pack(fill="both", expand=True)

        tk.Label(main, text="ScreenPlan", font=("Segoe UI", 24, "bold"),
                 fg=TEXT, bg=BG).pack(pady=(0, 4))
        tk.Label(main, text="登录你的账号", font=("Segoe UI", 12),
                 fg=TEXT_SEC, bg=BG).pack(pady=(0, 24))

        tk.Label(main, text="邮箱地址", font=("Segoe UI", 10, "bold"),
                 fg=TEXT_SEC, bg=BG, anchor="w").pack(fill="x")
        self.email_var = tk.StringVar()
        email_entry = tk.Entry(main, textvariable=self.email_var, font=("Segoe UI", 13),
                              bg="white", fg=TEXT, relief="solid", bd=1)
        email_entry.pack(fill="x", pady=(4, 12), ipady=6)

        tk.Label(main, text="密码", font=("Segoe UI", 10, "bold"),
                 fg=TEXT_SEC, bg=BG, anchor="w").pack(fill="x")
        self.pass_var = tk.StringVar()
        pass_entry = tk.Entry(main, textvariable=self.pass_var, show="•", font=("Segoe UI", 13),
                             bg="white", fg=TEXT, relief="solid", bd=1)
        pass_entry.pack(fill="x", pady=(4, 20), ipady=6)

        login_btn = tk.Button(main, text="登 录", font=("Segoe UI", 13, "bold"),
                             bg=BRAND, fg="white", activebackground=BRAND_HOVER,
                             activeforeground="white", relief="flat", cursor="hand2",
                             command=self._do_login)
        login_btn.pack(fill="x", ipady=8, pady=(0, 12))

        reg_btn = tk.Button(main, text="没有账号？在网页端注册",
                           font=("Segoe UI", 11),
                           bg=BG, fg=BRAND, relief="flat", cursor="hand2",
                           activebackground=BG, activeforeground=BRAND_HOVER,
                           command=self._open_web_register)
        reg_btn.pack()

        self.error_var = tk.StringVar()
        tk.Label(main, textvariable=self.error_var, font=("Segoe UI", 11),
                 fg="#dc2626", bg=BG).pack(pady=(12, 0))

        self.root.bind('<Return>', lambda e: self._do_login())

        email_entry.focus_set()

        self.root.mainloop()

    def _do_login(self):
        from network import login, save_token

        email = self.email_var.get().strip()
        password = self.pass_var.get().strip()

        if not email or not password:
            self.error_var.set("请输入邮箱和密码")
            return

        try:
            resp = login(email, password)
            if resp:
                save_token(resp.access_token)
                self.root.destroy()
                self.on_success(resp.access_token, resp.display_name)
            else:
                self.error_var.set("登录失败，请检查账号密码或网络连接")
        except Exception as e:
            self.error_var.set(f"错误: {str(e)}")

    def _open_web_register(self):
        from network import get_backend_url
        url = get_backend_url()
        if url:
            webbrowser.open(url)
