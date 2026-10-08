from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_NAME = "简易视频下载器"
APP_VERSION = "1.1.0"
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "YtDlpGUI"
SETTINGS_FILE = APP_DIR / "settings.json"
DEFAULT_OUTPUT = Path.home() / "Downloads"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def find_program(name: str, extra: list[Path] | None = None) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in extra or []:
        if candidate.exists():
            return str(candidate)
    return None


def application_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_ytdlp() -> str | None:
    return find_program(
        "yt-dlp",
        [
            application_dir() / "tools" / "yt-dlp.exe",
            Path.home() / ".local" / "bin" / "yt-dlp.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "yt-dlp" / "yt-dlp.exe",
        ],
    )


def runtime_environment() -> dict[str, str]:
    """Make packaged tools visible even before Explorer refreshes its PATH."""
    env = os.environ.copy()
    paths = [application_dir() / "tools", Path.home() / ".local" / "bin"]
    packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if packages.is_dir():
        paths.extend(packages.glob("Gyan.FFmpeg_*/*/bin"))
        paths.extend(packages.glob("DenoLand.Deno_*"))
    current = env.get("PATH", "")
    additions = [str(path) for path in paths if path.is_dir()]
    env["PATH"] = os.pathsep.join(additions + [current])
    return env


class DownloaderApp:
    QUALITY_MAP = {
        "最佳画质": None,
        "最高 2160p (4K)": 2160,
        "最高 1440p (2K)": 1440,
        "最高 1080p": 1080,
        "最高 720p": 720,
        "最高 480p": 480,
    }
    MODE_MAP = {
        "视频（自动选择最佳格式）": "video",
        "MP4 视频（优先兼容性）": "mp4",
        "MP3 音频": "mp3",
        "M4A 音频": "m4a",
    }
    COOKIE_MAP = {
        "不使用": "",
        "Chrome": "chrome",
        "Edge": "edge",
        "Firefox": "firefox",
    }

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("840x690")
        self.root.minsize(720, 590)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None
        self.worker: threading.Thread | None = None
        self.last_file: Path | None = None
        self.settings = self.load_settings()

        self.url_var = tk.StringVar()
        self.output_var = tk.StringVar(value=self.settings.get("output", str(DEFAULT_OUTPUT)))
        self.mode_var = tk.StringVar(value=self.settings.get("mode", "视频（自动选择最佳格式）"))
        self.quality_var = tk.StringVar(value=self.settings.get("quality", "最佳画质"))
        self.cookies_var = tk.StringVar(value=self.settings.get("cookies", "不使用"))
        self.playlist_var = tk.BooleanVar(value=self.settings.get("playlist", False))
        self.metadata_var = tk.BooleanVar(value=self.settings.get("metadata", True))
        self.status_var = tk.StringVar(value="准备就绪")
        self.percent_var = tk.DoubleVar(value=0)

        self.configure_style()
        self.build_ui()
        self.root.after(100, self.poll_events)
        self.root.after(250, self.url_entry.focus_set)

    def configure_style(self) -> None:
        self.root.configure(bg="#f4f6fa")
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 20, "bold"), foreground="#172033")
        style.configure("Sub.TLabel", font=("Microsoft YaHei UI", 9), foreground="#657089")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Card.TLabel", background="#ffffff", font=("Microsoft YaHei UI", 9))
        style.configure("Card.TCheckbutton", background="#ffffff", font=("Microsoft YaHei UI", 9))
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(18, 8))
        style.configure("Tool.TButton", font=("Microsoft YaHei UI", 9), padding=(9, 5))
        style.configure("Status.TLabel", background="#ffffff", foreground="#3154a4", font=("Microsoft YaHei UI", 9))

    def build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=(28, 20, 28, 18))
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container)
        header.pack(fill="x", pady=(0, 15))
        ttk.Label(header, text="简易视频下载器", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="由 yt-dlp 驱动 · 支持数千个视频和音频网站",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        card = ttk.Frame(container, style="Card.TFrame", padding=18)
        card.pack(fill="x")
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="视频或播放列表网址", style="Card.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        self.url_entry = ttk.Entry(card, textvariable=self.url_var, font=("Segoe UI", 10))
        self.url_entry.grid(row=1, column=0, sticky="ew", pady=(6, 14), ipady=6)
        self.url_entry.bind("<Return>", lambda _event: self.start_download())
        ttk.Button(card, text="粘贴", style="Tool.TButton", command=self.paste_url).grid(row=1, column=1, padx=(8, 0), pady=(6, 14))
        ttk.Button(card, text="清空", style="Tool.TButton", command=lambda: self.url_var.set("")).grid(row=1, column=2, padx=(8, 0), pady=(6, 14))

        ttk.Label(card, text="保存到", style="Card.TLabel").grid(row=2, column=0, columnspan=3, sticky="w")
        ttk.Entry(card, textvariable=self.output_var).grid(row=3, column=0, sticky="ew", pady=(6, 14), ipady=5)
        ttk.Button(card, text="选择目录", style="Tool.TButton", command=self.choose_output).grid(row=3, column=1, padx=(8, 0), pady=(6, 14))
        ttk.Button(card, text="打开目录", style="Tool.TButton", command=self.open_output).grid(row=3, column=2, padx=(8, 0), pady=(6, 14))

        options = ttk.Frame(card, style="Card.TFrame")
        options.grid(row=4, column=0, columnspan=3, sticky="ew")
        options.columnconfigure((0, 1, 2), weight=1)

        ttk.Label(options, text="下载类型", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(options, text="视频清晰度", style="Card.TLabel").grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Label(options, text="浏览器 Cookie", style="Card.TLabel").grid(row=0, column=2, sticky="w", padx=(12, 0))

        self.mode_combo = ttk.Combobox(options, textvariable=self.mode_var, values=list(self.MODE_MAP), state="readonly")
        self.mode_combo.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        self.mode_combo.bind("<<ComboboxSelected>>", self.on_mode_changed)
        self.quality_combo = ttk.Combobox(options, textvariable=self.quality_var, values=list(self.QUALITY_MAP), state="readonly")
        self.quality_combo.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=(6, 8))
        ttk.Combobox(options, textvariable=self.cookies_var, values=list(self.COOKIE_MAP), state="readonly").grid(
            row=1, column=2, sticky="ew", padx=(12, 0), pady=(6, 8)
        )

        checks = ttk.Frame(card, style="Card.TFrame")
        checks.grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 2))
        ttk.Checkbutton(checks, text="下载整个播放列表", variable=self.playlist_var, style="Card.TCheckbutton").pack(side="left")
        ttk.Checkbutton(checks, text="写入缩略图和元数据", variable=self.metadata_var, style="Card.TCheckbutton").pack(side="left", padx=(22, 0))

        action_bar = ttk.Frame(container, padding=(0, 14, 0, 10))
        action_bar.pack(fill="x")
        self.start_button = ttk.Button(action_bar, text="开始下载", style="Primary.TButton", command=self.start_download)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(action_bar, text="取消", style="Tool.TButton", state="disabled", command=self.cancel_download)
        self.cancel_button.pack(side="left", padx=(9, 0))
        ttk.Button(action_bar, text="更新 yt-dlp", style="Tool.TButton", command=self.update_ytdlp).pack(side="right")

        progress_card = ttk.Frame(container, style="Card.TFrame", padding=(16, 12))
        progress_card.pack(fill="x", pady=(0, 12))
        progress_card.columnconfigure(0, weight=1)
        ttk.Label(progress_card, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(progress_card, variable=self.percent_var, maximum=100)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        log_frame = ttk.LabelFrame(container, text="运行日志", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(
            log_frame,
            height=10,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
            bg="#111827",
            fg="#dbe7ff",
            insertbackground="white",
            relief="flat",
            padx=10,
            pady=8,
        )
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.on_mode_changed()

    def load_settings(self) -> dict[str, object]:
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}

    def save_settings(self) -> None:
        data = {
            "output": self.output_var.get().strip(),
            "mode": self.mode_var.get(),
            "quality": self.quality_var.get(),
            "cookies": self.cookies_var.get(),
            "playlist": self.playlist_var.get(),
            "metadata": self.metadata_var.get(),
        }
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def paste_url(self) -> None:
        try:
            text = self.root.clipboard_get().strip()
        except tk.TclError:
            messagebox.showinfo(APP_NAME, "剪贴板里没有可用的文字。")
            return
        self.url_var.set(text)
        self.url_entry.icursor("end")

    def choose_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_var.get() or str(DEFAULT_OUTPUT))
        if selected:
            self.output_var.set(selected)

    def open_output(self) -> None:
        path = Path(self.output_var.get().strip() or DEFAULT_OUTPUT)
        try:
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(path)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"无法打开目录：\n{exc}")

    def on_mode_changed(self, _event: object | None = None) -> None:
        audio = self.MODE_MAP.get(self.mode_var.get(), "video") in {"mp3", "m4a"}
        self.quality_combo.configure(state="disabled" if audio else "readonly")

    def build_command(self) -> list[str]:
        ytdlp = find_ytdlp()
        if not ytdlp:
            raise RuntimeError("找不到 yt-dlp。请先安装 yt-dlp，或将它加入 PATH。")

        url = self.url_var.get().strip()
        if not url:
            raise ValueError("请先粘贴视频或播放列表网址。")
        if not re.match(r"^https?://", url, re.IGNORECASE):
            raise ValueError("网址需要以 http:// 或 https:// 开头。")

        output = Path(self.output_var.get().strip() or DEFAULT_OUTPUT).expanduser()
        output.mkdir(parents=True, exist_ok=True)
        if not output.is_dir():
            raise ValueError("保存路径不是一个有效目录。")

        cmd = [
            ytdlp,
            "--newline",
            "--encoding",
            "utf-8",
            "--progress",
            "--no-simulate",
            "--windows-filenames",
            "--trim-filenames",
            "180",
            "--progress-template",
            "download:__PROGRESS__:%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
            "--print",
            "after_move:__FILE__:%(filepath)s",
            "-P",
            str(output),
            "-o",
            "%(title)s [%(id)s].%(ext)s",
        ]

        if not self.playlist_var.get():
            cmd.append("--no-playlist")

        cookies = self.COOKIE_MAP.get(self.cookies_var.get(), "")
        if cookies:
            cmd.extend(["--cookies-from-browser", cookies])

        mode = self.MODE_MAP.get(self.mode_var.get(), "video")
        max_height = self.QUALITY_MAP.get(self.quality_var.get())
        height_filter = f"[height<={max_height}]" if max_height else ""
        if mode == "video":
            cmd.extend(["-f", f"bv*{height_filter}+ba/b{height_filter}"])
        elif mode == "mp4":
            cmd.extend(
                [
                    "-f",
                    f"bv*[ext=mp4]{height_filter}+ba[ext=m4a]/b[ext=mp4]{height_filter}/bv*{height_filter}+ba/b{height_filter}",
                    "--merge-output-format",
                    "mp4",
                ]
            )
        elif mode in {"mp3", "m4a"}:
            cmd.extend(["-x", "--audio-format", mode, "--audio-quality", "0"])

        if self.metadata_var.get():
            cmd.extend(["--embed-metadata", "--embed-thumbnail"])

        cmd.append(url)
        return cmd

    def start_download(self) -> None:
        if self.process is not None:
            return
        try:
            cmd = self.build_command()
        except (ValueError, RuntimeError, OSError) as exc:
            messagebox.showwarning(APP_NAME, str(exc))
            return

        self.save_settings()
        self.last_file = None
        self.percent_var.set(0)
        self.progress.configure(mode="determinate")
        self.clear_log()
        self.append_log("开始任务…\n")
        self.status_var.set("正在准备下载…")
        self.set_running(True)
        self.worker = threading.Thread(target=self.run_process, args=(cmd, "download"), daemon=True)
        self.worker.start()

    def update_ytdlp(self) -> None:
        if self.process is not None:
            messagebox.showinfo(APP_NAME, "请等待当前任务结束后再更新。")
            return
        ytdlp = find_ytdlp()
        if not ytdlp:
            messagebox.showerror(APP_NAME, "找不到 yt-dlp。")
            return
        self.clear_log()
        self.append_log("正在检查 yt-dlp 更新…\n")
        self.status_var.set("正在更新 yt-dlp…")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.set_running(True)
        self.worker = threading.Thread(target=self.run_process, args=([ytdlp, "-U"], "update"), daemon=True)
        self.worker.start()

    def run_process(self, cmd: list[str], kind: str) -> None:
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
                env=runtime_environment(),
            )
            self.process = process
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.rstrip("\r\n")
                self.events.put(("line", line))
            return_code = process.wait()
            self.events.put(("done", (return_code, kind)))
        except Exception as exc:  # Keep failures visible in the GUI.
            self.events.put(("error", str(exc)))

    def cancel_download(self) -> None:
        process = self.process
        if process is None:
            return
        if not messagebox.askyesno(APP_NAME, "确定要取消当前任务吗？"):
            return
        self.status_var.set("正在取消…")
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
        except OSError:
            process.terminate()

    def poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "line":
                    self.handle_line(str(payload))
                elif event == "done":
                    code, kind = payload  # type: ignore[misc]
                    self.finish_process(int(code), str(kind))
                elif event == "error":
                    self.process = None
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                    self.set_running(False)
                    self.status_var.set("任务启动失败")
                    self.append_log(f"错误：{payload}\n")
                    messagebox.showerror(APP_NAME, f"任务启动失败：\n{payload}")
        except queue.Empty:
            pass
        self.root.after(100, self.poll_events)

    def handle_line(self, line: str) -> None:
        clean = re.sub(r"\x1b\[[0-9;]*m", "", line)
        if clean.startswith("__PROGRESS__:"):
            values = clean.partition(":")[2].split("|", 2)
            percent_text = values[0].strip().replace("%", "")
            try:
                percent = float(percent_text)
                self.percent_var.set(max(0, min(100, percent)))
            except ValueError:
                pass
            speed = values[1].strip() if len(values) > 1 else ""
            eta = values[2].strip() if len(values) > 2 else ""
            details = " · ".join(part for part in [f"{percent_text}%", speed, f"剩余 {eta}" if eta and eta != "NA" else ""] if part)
            self.status_var.set(f"正在下载 · {details}")
            return
        if clean.startswith("__FILE__:"):
            self.last_file = Path(clean.partition(":")[2])
            self.append_log(f"已保存：{self.last_file}\n")
            return
        self.append_log(clean + "\n")
        if "[download] Destination:" in clean or "[Merger]" in clean:
            self.status_var.set("正在处理媒体文件…")

    def finish_process(self, code: int, kind: str) -> None:
        self.process = None
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.set_running(False)
        if code == 0:
            self.percent_var.set(100)
            if kind == "update":
                self.status_var.set("yt-dlp 已是最新版本")
                messagebox.showinfo(APP_NAME, "yt-dlp 更新检查完成。")
            else:
                self.status_var.set("下载完成")
                if messagebox.askyesno(APP_NAME, "下载完成！\n\n是否打开保存目录？"):
                    self.open_output()
        else:
            self.status_var.set("任务失败，请查看运行日志")
            messagebox.showerror(
                APP_NAME,
                "任务没有成功完成。请查看窗口下方的运行日志。\n\n"
                "如果 YouTube 要求登录，请在“浏览器 Cookie”中选择你已登录的浏览器后重试。",
            )

    def set_running(self, running: bool) -> None:
        self.start_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")

    def clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def on_close(self) -> None:
        if self.process is not None:
            if not messagebox.askyesno(APP_NAME, "下载仍在进行。确定要退出并取消任务吗？"):
                return
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW,
                    check=False,
                )
            except OSError:
                pass
        self.save_settings()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    if getattr(sys, "frozen", False):
        try:
            root.iconbitmap(default=sys.executable)
        except tk.TclError:
            pass
    root.option_add("*Font", "{Microsoft YaHei UI} 9")
    DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
