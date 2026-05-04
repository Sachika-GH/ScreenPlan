"""Setup window - tkinter-based login/register UI matching web panel design."""

import tkinter as tk
from tkinter import ttk
import webbrowser


class SetupWindow:
    """Styled login/register window for first-time setup."""

    def __init__(self, on_success):
        self.on_success = on_success
        self.token = None
        self._build()

    def _build(self):
        self.root = tk.Tk()
        self.root.title("ScreenPlan - Setup")
        self.root.geometry("400x520")
        self.root.configure(bg="#f4f6f9")
        self.root.resizable(False, False)

        BG = "#f4f6f9"
        SURFACE = "#ffffff"
        BRAND = "#2563EB"
        BRAND_HOVER = "#1E3A5F"
        TEXT = "#111827"
        TEXT_SEC = "#4b5563"
        BORDER = "#e5e7eb"

        main = tk.Frame(self.root, bg=BG, padx=32, pady=32)
        main.pack(fill="both", expand=True)

        tk.Label(main, text="ScreenPlan", font=("Helvetica Neue", 24, "bold"),
                 fg=TEXT, bg=BG).pack(pady=(0, 4))
        tk.Label(main, text="Login to your account", font=("Helvetica Neue", 12),
                 fg=TEXT_SEC, bg=BG).pack(pady=(0, 24))

        tk.Label(main, text="Email", font=("Helvetica Neue", 10, "bold"),
                 fg=TEXT_SEC, bg=BG, anchor="w").pack(fill="x")
        self.email_var = tk.StringVar()
        e = tk.Entry(main, textvariable=self.email_var, font=("Helvetica Neue", 13),
                     bg="white", fg=TEXT, relief="solid", bd=1)
        e.pack(fill="x", pady=(4, 12), ipady=6)
        self._style_entry(e, BORDER)

        tk.Label(main, text="Password", font=("Helvetica Neue", 10, "bold"),
                 fg=TEXT_SEC, bg=BG, anchor="w").pack(fill="x")
        self.pass_var = tk.StringVar()
        p = tk.Entry(main, textvariable=self.pass_var, show="\u2022", font=("Helvetica Neue", 13),
                     bg="white", fg=TEXT, relief="solid", bd=1)
        p.pack(fill="x", pady=(4, 20), ipady=6)
        self._style_entry(p, BORDER)

        btn = tk.Button(main, text="Login", font=("Helvetica Neue", 13, "bold"),
                        bg=BRAND, fg="white", activebackground=BRAND_HOVER,
                        activeforeground="white", relief="flat", cursor="hand2",
                        command=self._do_login)
        btn.pack(fill="x", ipady=8, pady=(0, 12))

        reg_btn = tk.Button(main, text="No account? Register on the web",
                            font=("Helvetica Neue", 11),
                            bg=BG, fg=BRAND, relief="flat", cursor="hand2",
                            activebackground=BG, activeforeground=BRAND_HOVER,
                            command=self._open_web_register)
        reg_btn.pack()

        self.error_var = tk.StringVar()
        tk.Label(main, textvariable=self.error_var, font=("Helvetica Neue", 11),
                 fg="#dc2626", bg=BG).pack(pady=(12, 0))

        self.root.mainloop()

    @staticmethod
    def _style_entry(entry, border_color):
        entry.configure(highlightbackground=border_color, highlightcolor="#2563EB",
                        highlightthickness=1, insertbackground="#2563EB")

    def _do_login(self):
        from network import login, save_token

        email = self.email_var.get().strip()
        password = self.pass_var.get().strip()

        if not email or not password:
            self.error_var.set("Please enter email and password")
            return

        try:
            resp = login(email, password)
            if resp:
                save_token(resp.access_token)
                self.root.destroy()
                self.on_success(resp.access_token, resp.display_name)
            else:
                self.error_var.set("Login failed. Check credentials or network.")
        except Exception as e:
            self.error_var.set(f"Error: {e}")

    def _open_web_register(self):
        from network import get_backend_url
        url = get_backend_url()
        if url:
            webbrowser.open(url)
