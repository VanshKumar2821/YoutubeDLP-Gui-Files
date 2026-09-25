import os, sys, subprocess, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox

BG, BG2, FG, ACCENT, SUB = "#121212", "#1e1e1e", "#e8e8e8", "#7c5cff", "#8a8a8a"

RES = {
    "Best Quality": "bv*+ba/b",
    "2160p (4K)": "bv*[height<=2160]+ba/b[height<=2160]",
    "1440p (2K)": "bv*[height<=1440]+ba/b[height<=1440]",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p": "bv*[height<=720]+ba/b[height<=720]",
    "480p": "bv*[height<=480]+ba/b[height<=480]",
    "360p": "bv*[height<=360]+ba/b[height<=360]",
    "Audio Only (MP3)": "AUDIO",
}

def app_dir():
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    d = os.path.join(base, "YTDownloader")
    os.makedirs(d, exist_ok=True)
    return d

def ytdlp_path():
    p = os.path.join(app_dir(), "yt-dlp.exe")
    if os.path.exists(p):
        return p
    local = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "yt-dlp.exe")
    return local if os.path.exists(local) else "yt-dlp.exe"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Downloader")
        self.geometry("560x420")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.out_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=BG2, background=BG2,
                         foreground=FG, arrowcolor=FG, borderwidth=0)
        self.option_add("*TCombobox*Listbox*Background", BG2)
        self.option_add("*TCombobox*Listbox*Foreground", FG)
        style.configure("TProgressbar", troughcolor=BG2, background=ACCENT,
                         thickness=6, borderwidth=0)

        tk.Label(self, text="YT DOWNLOADER", bg=BG, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack(pady=(20, 4))
        tk.Label(self, text="paste a link, pick a resolution, go",
                 bg=BG, fg=SUB, font=("Segoe UI", 9)).pack(pady=(0, 16))

        frm = tk.Frame(self, bg=BG)
        frm.pack(padx=30, fill="x")

        tk.Label(frm, text="VIDEO LINK", bg=BG, fg=SUB,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.url = tk.Entry(frm, bg=BG2, fg=FG, insertbackground=FG,
                             relief="flat", font=("Segoe UI", 10))
        self.url.pack(fill="x", ipady=8, pady=(4, 14))

        tk.Label(frm, text="RESOLUTION", bg=BG, fg=SUB,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.res = ttk.Combobox(frm, values=list(RES.keys()), state="readonly",
                                 style="TCombobox", font=("Segoe UI", 10))
        self.res.current(0)
        self.res.pack(fill="x", ipady=6, pady=(4, 14))

        row = tk.Frame(frm, bg=BG)
        row.pack(fill="x", pady=(0, 14))
        tk.Label(row, text="SAVE TO", bg=BG, fg=SUB,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        r2 = tk.Frame(row, bg=BG)
        r2.pack(fill="x", pady=(4, 0))
        self.dir_lbl = tk.Label(r2, text=self.out_dir, bg=BG2, fg=FG, anchor="w",
                                 font=("Segoe UI", 9), padx=8)
        self.dir_lbl.pack(side="left", fill="x", expand=True, ipady=7)
        tk.Button(r2, text="Browse", command=self.browse, bg=BG2, fg=FG,
                  relief="flat", activebackground=ACCENT, padx=10).pack(side="left", padx=(6, 0))

        self.btn = tk.Button(frm, text="DOWNLOAD", command=self.start,
                              bg=ACCENT, fg="white", relief="flat",
                              font=("Segoe UI", 10, "bold"), activebackground="#6a4ce0")
        self.btn.pack(fill="x", ipady=10, pady=(4, 12))

        self.bar = ttk.Progressbar(frm, mode="indeterminate", style="TProgressbar")
        self.bar.pack(fill="x")

        self.status = tk.Label(self, text="Ready", bg=BG, fg=SUB, font=("Segoe UI", 9))
        self.status.pack(pady=10)

    def browse(self):
        d = filedialog.askdirectory()
        if d:
            self.out_dir = d
            self.dir_lbl.config(text=d)

    def start(self):
        url = self.url.get().strip()
        if not url:
            messagebox.showwarning("Missing link", "Paste a video link first.")
            return
        self.btn.config(state="disabled", text="DOWNLOADING...")
        self.bar.start(12)
        self.status.config(text="Working...")
        threading.Thread(target=self.run_download, args=(url,), daemon=True).start()

    def run_download(self, url):
        choice = RES.get(self.res.get(), "bv*+ba/b")
        cmd = [ytdlp_path(), "-o", os.path.join(self.out_dir, "%(title)s.%(ext)s")]
        ffmpeg = os.path.join(app_dir(), "ffmpeg.exe")
        if os.path.exists(ffmpeg):
            cmd += ["--ffmpeg-location", app_dir()]
        if choice == "AUDIO":
            cmd += ["-x", "--audio-format", "mp3"]
        else:
            cmd += ["-f", choice, "--merge-output-format", "mp4"]
        cmd.append(url)
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
            ok = proc.returncode == 0
        except FileNotFoundError:
            ok, proc = False, None
            self.after(0, lambda: messagebox.showerror(
                "yt-dlp.exe not found",
                "Setup did not finish correctly. Please restart the app."))
        self.after(0, self.finish, ok, proc)

    def finish(self, ok, proc):
        self.bar.stop()
        self.btn.config(state="normal", text="DOWNLOAD")
        if ok:
            self.status.config(text="Done — saved to " + self.out_dir)
        else:
            self.status.config(text="Failed. Check the link and try again.")
            if proc and proc.stderr:
                print(proc.stderr)

if __name__ == "__main__":
    App().mainloop()
