"""Tkinter desktop interface for batch OGG to WAV conversion."""

from __future__ import annotations

import concurrent.futures
import queue
import shutil
import threading
from pathlib import Path
from typing import Optional

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except ImportError:
    tk = None
    filedialog = messagebox = scrolledtext = ttk = None

from .cli import ConversionResult, build_jobs, convert_one, find_ogg_files


class OggToWavGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("OGG 批量转 WAV")
        self.root.geometry("760x560")
        self.root.minsize(680, 500)

        self.events: queue.Queue = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.total = 0
        self.completed = 0

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.ffmpeg_var = tk.StringVar(value="ffmpeg")
        self.jobs_var = tk.IntVar(value=4)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.flat_var = tk.BooleanVar(value=False)
        self.sample_rate_var = tk.StringVar(value="")
        self.channels_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="请选择 OGG 文件或目录")

        self._build_ui()
        self.root.after(100, self._poll_events)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(1, weight=1)

        ttk.Label(container, text="输入").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(container, textvariable=self.input_var).grid(row=0, column=1, sticky=tk.EW, padx=8, pady=4)
        input_buttons = ttk.Frame(container)
        input_buttons.grid(row=0, column=2, sticky=tk.E, pady=4)
        ttk.Button(input_buttons, text="选择文件", command=self._choose_input_file).pack(side=tk.LEFT)
        ttk.Button(input_buttons, text="选择目录", command=self._choose_input_dir).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(container, text="输出目录").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(container, textvariable=self.output_var).grid(row=1, column=1, sticky=tk.EW, padx=8, pady=4)
        ttk.Button(container, text="选择目录", command=self._choose_output_dir).grid(row=1, column=2, sticky=tk.E, pady=4)
        ttk.Label(container, text="留空则在原 OGG 文件旁生成 WAV", foreground="#666").grid(
            row=2, column=1, sticky=tk.W, padx=8
        )

        options = ttk.LabelFrame(container, text="转换选项", padding=10)
        options.grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=(12, 8))
        options.columnconfigure(5, weight=1)

        ttk.Label(options, text="并发数").grid(row=0, column=0, sticky=tk.W)
        tk.Spinbox(options, from_=1, to=16, width=5, textvariable=self.jobs_var).grid(row=0, column=1, sticky=tk.W, padx=(6, 18))
        ttk.Checkbutton(options, text="覆盖已有 WAV", variable=self.overwrite_var).grid(row=0, column=2, sticky=tk.W, padx=(0, 18))
        ttk.Checkbutton(options, text="平铺输出", variable=self.flat_var).grid(row=0, column=3, sticky=tk.W, padx=(0, 18))

        ttk.Label(options, text="采样率").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        ttk.Combobox(
            options,
            textvariable=self.sample_rate_var,
            values=("", "44100", "48000"),
            width=8,
        ).grid(row=1, column=1, sticky=tk.W, padx=(6, 18), pady=(10, 0))
        ttk.Label(options, text="声道").grid(row=1, column=2, sticky=tk.W, pady=(10, 0))
        ttk.Combobox(
            options,
            textvariable=self.channels_var,
            values=("", "1", "2"),
            width=5,
        ).grid(row=1, column=3, sticky=tk.W, padx=(6, 18), pady=(10, 0))
        ttk.Label(options, text="留空则保留原音频参数", foreground="#666").grid(row=1, column=4, columnspan=2, sticky=tk.W, pady=(10, 0))

        ttk.Label(container, text="ffmpeg").grid(row=4, column=0, sticky=tk.W, pady=4)
        ttk.Entry(container, textvariable=self.ffmpeg_var).grid(row=4, column=1, sticky=tk.EW, padx=8, pady=4)
        ttk.Button(container, text="浏览", command=self._choose_ffmpeg).grid(row=4, column=2, sticky=tk.E, pady=4)

        action_row = ttk.Frame(container)
        action_row.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(12, 8))
        self.start_button = ttk.Button(action_row, text="开始转换", command=self.start_conversion)
        self.start_button.pack(side=tk.LEFT)
        ttk.Label(action_row, textvariable=self.status_var).pack(side=tk.LEFT, padx=12)

        self.progress = ttk.Progressbar(container, mode="determinate")
        self.progress.grid(row=6, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))

        self.log = scrolledtext.ScrolledText(container, height=15, state=tk.DISABLED, wrap=tk.WORD)
        self.log.grid(row=7, column=0, columnspan=3, sticky=tk.NSEW)
        container.rowconfigure(7, weight=1)

    def _choose_input_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("OGG 音频", "*.ogg"), ("所有文件", "*.*")])
        if path:
            self.input_var.set(path)

    def _choose_input_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.input_var.set(path)

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_var.set(path)

    def _choose_ffmpeg(self) -> None:
        path = filedialog.askopenfilename()
        if path:
            self.ffmpeg_var.set(path)

    def _append_log(self, text: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _parse_optional_int(self, value: str, label: str) -> Optional[int]:
        value = value.strip()
        if not value:
            return None
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(f"{label}必须是数字") from exc
        if parsed <= 0:
            raise ValueError(f"{label}必须是正整数")
        return parsed

    def start_conversion(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        input_text = self.input_var.get().strip()
        if not input_text:
            messagebox.showerror("缺少输入", "请选择 OGG 文件或目录")
            return
        ffmpeg = self.ffmpeg_var.get().strip() or "ffmpeg"
        if shutil.which(ffmpeg) is None and not Path(ffmpeg).exists():
            messagebox.showerror("找不到 ffmpeg", "请安装 ffmpeg，或在界面中选择 ffmpeg 可执行文件")
            return

        try:
            sample_rate = self._parse_optional_int(self.sample_rate_var.get(), "采样率")
            channels = self._parse_optional_int(self.channels_var.get(), "声道")
            jobs_count = int(self.jobs_var.get())
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("参数错误", str(exc))
            return
        if channels not in (None, 1, 2):
            messagebox.showerror("参数错误", "声道只能填写 1 或 2")
            return
        if jobs_count <= 0:
            messagebox.showerror("参数错误", "并发数必须是正整数")
            return

        output_text = self.output_var.get().strip()
        output_dir = Path(output_text).expanduser().resolve() if output_text else None
        input_path = Path(input_text).expanduser().resolve()

        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)
        self.progress.configure(value=0, maximum=1)
        self.completed = 0
        self.total = 0
        self.converted = 0
        self.skipped = 0
        self.failures = 0
        overwrite = self.overwrite_var.get()
        flat = self.flat_var.get()
        self.status_var.set("正在扫描 OGG 文件...")
        self.start_button.configure(state=tk.DISABLED)

        self.worker = threading.Thread(
            target=self._conversion_worker,
            args=(input_path, output_dir, ffmpeg, jobs_count, sample_rate, channels, overwrite, flat),
            daemon=True,
        )
        self.worker.start()

    def _conversion_worker(
        self,
        input_path: Path,
        output_dir: Optional[Path],
        ffmpeg: str,
        jobs_count: int,
        sample_rate: Optional[int],
        channels: Optional[int],
        overwrite: bool,
        flat: bool,
    ) -> None:
        try:
            sources = find_ogg_files(input_path)
            if not sources:
                self.events.put(("empty", f"未找到 OGG 文件：{input_path}"))
                return
            jobs = build_jobs(sources, input_path, output_dir, flat=flat)
            self.events.put(("total", len(jobs)))
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs_count) as executor:
                futures = [
                    executor.submit(
                        convert_one,
                        job,
                        ffmpeg=ffmpeg,
                        overwrite=overwrite,
                        sample_rate=sample_rate,
                        channels=channels,
                    )
                    for job in jobs
                ]
                for future in concurrent.futures.as_completed(futures):
                    self.events.put(("result", future.result()))
            self.events.put(("done", None))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "total":
                    self.total = payload
                    self.progress.configure(maximum=max(1, self.total))
                    self.status_var.set(f"正在转换 {self.total} 个文件...")
                elif event == "result":
                    self._handle_result(payload)
                elif event == "done":
                    failures = getattr(self, "failures", 0)
                    converted = getattr(self, "converted", 0)
                    skipped = getattr(self, "skipped", 0)
                    self.status_var.set(f"完成：成功 {converted}，跳过 {skipped}，失败 {failures}")
                    self._append_log(f"汇总：成功 {converted}，跳过 {skipped}，失败 {failures}，共 {self.total}")
                    self.start_button.configure(state=tk.NORMAL)
                elif event == "empty":
                    self.status_var.set(payload)
                    self._append_log(payload)
                    self.start_button.configure(state=tk.NORMAL)
                elif event == "error":
                    self.status_var.set("转换失败")
                    self._append_log(f"错误：{payload}")
                    self.start_button.configure(state=tk.NORMAL)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _handle_result(self, result: ConversionResult) -> None:
        self.completed += 1
        if result.skipped:
            self.skipped += 1
            status = "跳过"
        elif result.ok:
            self.converted += 1
            status = "完成"
        else:
            self.failures += 1
            status = "失败"
        self.progress.configure(value=self.completed)
        self.status_var.set(f"进度 {self.completed}/{self.total}")
        line = f"[{status}] {result.job.source} -> {result.job.target}"
        if not result.ok and result.message:
            line += f"\n    {result.message}"
        self._append_log(line)


def main() -> None:
    if tk is None:
        raise SystemExit("当前 Python 未安装 Tkinter；Ubuntu/Debian 请先运行 sudo apt install python3-tk")
    root = tk.Tk()
    OggToWavGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
