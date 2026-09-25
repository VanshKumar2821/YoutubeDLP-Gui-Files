import os, sys, re, json, subprocess, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox

BG, BG2, FG, ACCENT, SUB = "#121212", "#1e1e1e", "#e8e8e8", "#7c5cff", "#8a8a8a"
PLACEHOLDER = "Enter a link above"
CHECKING = "Checking link..."

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

def np_kwargs():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}

STD_HEIGHTS = [144, 240, 360, 480, 540, 576, 720, 900, 1080, 1440, 2160, 4320]

def nearest_std(h):
    return min(STD_HEIGHTS, key=lambda s: abs(s - h))
    if not n:
        return ""
    mb = n / 1_000_000
    return f" — {mb/1024:.2f} GB" if mb > 1024 else f" — {mb:.0f} MB"

def probe(url):
    """Return (list of (label, format_str), audio_label_or_None) or None if invalid."""
    cmd = [ytdlp_path(), "--no-warnings", "--skip-download", "-J", url]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=25, **np_kwargs())
    except Exception:
        return None
    if out.returncode != 0:
        return None
    try:
        data = json.loads(out.stdout)
    except Exception:
        return None
    formats = data.get("formats", [])
    if not formats:
        return None
    audio_sizes = [f.get("filesize") or f.get("filesize_approx") or 0
                   for f in formats if f.get("vcodec") == "none"]
    best_audio = max(audio_sizes, default=0)
    heights = {}
    for f in formats:
        h = f.get("height")
        if not h:
            continue
        size = f.get("filesize") or f.get("filesize_approx") or 0
        if f.get("acodec") == "none":
            size += best_audio
        if h not in heights or size > heights[h]:
            heights[h] = size
    # Bucket real heights into the nearest standard resolution for display,
    # keeping the best (highest real height / largest size) format per bucket.
    buckets = {}
    for h, size in heights.items():
        std = nearest_std(h)
        if std not in buckets or h > buckets[std][0]:
            buckets[std] = (h, size)
    items = []
    for std in sorted(buckets, reverse=True):
        real_h, size = buckets[std]
        tag = " (4K)" if std >= 2160 else " (2K)" if std >= 1440 else ""
        label = f"{std}p{tag}{fmt_size(size)}"
        items.append((label, f"bv*[height<={real_h}]+ba/b[height<={real_h}]"))
    audio_label = f"Audio Only (MP3){fmt_size(best_audio)}" if best_audio else "Audio Only (MP3)"
    items.append((audio_label, "AUDIO"))
    return items

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Downloader")
        self.geometry("560x420")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.out_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        self.formats = {}
        self._debounce = None
        self._probe_id = 0

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=BG2, background=BG2,
                         foreground=FG, arrowcolor=FG, borderwidth=0, padding=6)
        style.map("TCombobox",
                   fieldbackground=[("readonly", BG2), ("disabled", BG2)],
                   background=[("readonly", BG2), ("disabled", BG2)],
                   foreground=[("readonly", FG), ("disabled", SUB)],
                   selectbackground=[("readonly", BG2)],
                   selectforeground=[("readonly", FG)])
        self.option_add("*TCombobox*Listbox*Background", BG2)
        self.option_add("*TCombobox*Listbox*Foreground", FG)
        self.option_add("*TCombobox*Listbox*selectBackground", ACCENT)
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
        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", self.on_url_change)
        self.url = tk.Entry(frm, textvariable=self.url_var, bg=BG2, fg=FG,
                             insertbackground=FG, relief="flat", font=("Segoe UI", 10))
        self.url.pack(fill="x", ipady=8, pady=(4, 14))

        tk.Label(frm, text="RESOLUTION", bg=BG, fg=SUB,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.res = ttk.Combobox(frm, values=[PLACEHOLDER], state="disabled",
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

        self.bar = ttk.Progressbar(frm, mode="determinate", maximum=100, style="TProgressbar")
        self.bar.pack(fill="x")

        self.status = tk.Label(self, text="Ready", bg=BG, fg=SUB, font=("Segoe UI", 9))
        self.status.pack(pady=10)

    # ---- link watching ----
    def on_url_change(self, *_):
        if self._debounce:
            self.after_cancel(self._debounce)
        self._debounce = self.after(700, self.check_link)

    def check_link(self):
        url = self.url_var.get().strip()
        self._probe_id += 1
        pid = self._probe_id
        if not url:
            self.set_resolutions([], PLACEHOLDER)
            return
        self.set_resolutions([], CHECKING)
        threading.Thread(target=self._probe_thread, args=(url, pid), daemon=True).start()

    def _probe_thread(self, url, pid):
        items = probe(url)
        self.after(0, self._probe_done, items, pid)

    def _probe_done(self, items, pid):
        if pid != self._probe_id:
            return  # stale result from an older link
        if not items:
            self.set_resolutions([], "Invalid or unsupported link")
            return
        self.set_resolutions(items, None)

    def set_resolutions(self, items, placeholder):
        self.formats = {label: fmt for label, fmt in items}
        if placeholder:
            self.res.config(values=[placeholder], state="disabled")
            self.res.current(0)
        else:
            labels = list(self.formats.keys())
            self.res.config(values=labels, state="readonly")
            self.res.current(0)

    # ---- rest ----
    def browse(self):
        d = filedialog.askdirectory()
        if d:
            self.out_dir = d
            self.dir_lbl.config(text=d)

    def start(self):
        url = self.url_var.get().strip()
        if not url or not self.formats:
            messagebox.showwarning("No resolution", "Paste a valid link and wait for resolutions to load.")
            return
        self.btn.config(state="disabled", text="DOWNLOADING...")
        self.bar["value"] = 0
        self.status.config(text="Starting...")
        threading.Thread(target=self.run_download, args=(url, self.formats[self.res.get()]),
                          daemon=True).start()

    def run_download(self, url, choice):
        have_ffmpeg = os.path.exists(os.path.join(app_dir(), "ffmpeg.exe"))
        cmd = [ytdlp_path(), "-o", os.path.join(self.out_dir, "%(title)s.%(ext)s"),
               "--newline", "--no-warnings"]
        if have_ffmpeg:
            cmd += ["--ffmpeg-location", app_dir()]
        if choice == "AUDIO":
            cmd += ["-x", "--audio-format", "mp3"]
        else:
            cmd += ["-f", choice, "--merge-output-format", "mp4"]
        cmd.append(url)

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1, **np_kwargs())
        except FileNotFoundError:
            self.after(0, lambda: messagebox.showerror(
                "yt-dlp.exe not found", "Setup did not finish correctly. Please restart the app."))
            self.after(0, self.finish, False, "yt-dlp.exe not found")
            return

        last_line = ""
        for line in proc.stdout:
            line = line.strip()
            if line:
                last_line = line
            m = re.search(r"(\d+(?:\.\d+)?)%", line)
            if m:
                self.after(0, self.set_progress, float(m.group(1)))
        proc.wait()
        self.after(0, self.finish, proc.returncode == 0, last_line)

    def set_progress(self, pct):
        self.bar["value"] = pct
        self.status.config(text=f"Downloading... {pct:.0f}%")

    def finish(self, ok, last_line):
        self.btn.config(state="normal", text="DOWNLOAD")
        if ok:
            self.bar["value"] = 100
            self.status.config(text="Done — saved to " + self.out_dir)
        else:
            self.status.config(text="Failed — see download_error.log in app folder")
            try:
                with open(os.path.join(app_dir(), "download_error.log"), "w") as f:
                    f.write(last_line or "No output")
            except Exception:
                pass

if __name__ == "__main__":
    App().mainloop()
