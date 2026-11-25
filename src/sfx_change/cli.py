"""Command-line batch converter from OGG to WAV."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class ConversionJob:
    source: Path
    target: Path


@dataclass(frozen=True)
class ConversionResult:
    job: ConversionJob
    ok: bool
    skipped: bool = False
    message: str = ""


def find_ogg_files(input_path: Path) -> List[Path]:
    """Return all OGG files below a directory, or a single OGG file."""
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() == ".ogg" else []
    if not input_path.is_dir():
        raise FileNotFoundError(f"输入路径不存在：{input_path}")
    return sorted(
        path
        for path in input_path.rglob("*")
        if path.is_file() and path.suffix.lower() == ".ogg"
    )


def build_jobs(
    sources: Iterable[Path],
    input_path: Path,
    output_dir: Optional[Path],
    flat: bool = False,
) -> List[ConversionJob]:
    """Map each OGG file to its WAV output path."""
    jobs: List[ConversionJob] = []
    targets = {}
    for source in sources:
        if output_dir is None:
            target = source.with_suffix(".wav")
        else:
            if flat or input_path.is_file():
                relative = Path(source.name)
            else:
                relative = source.relative_to(input_path)
            target = output_dir / relative.with_suffix(".wav")
        target_key = os.path.normcase(str(target))
        if target_key in targets:
            raise ValueError(
                "多个输入会输出到同一个 WAV 文件："
                f"{targets[target_key]} 和 {source} -> {target}"
            )
        targets[target_key] = source
        jobs.append(ConversionJob(source=source, target=target))
    return jobs


def convert_one(
    job: ConversionJob,
    *,
    ffmpeg: str,
    overwrite: bool,
    sample_rate: Optional[int],
    channels: Optional[int],
) -> ConversionResult:
    if job.target.exists() and not overwrite:
        return ConversionResult(job, ok=True, skipped=True, message="目标文件已存在")

    job.target.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y" if overwrite else "-n"]
    command.extend(["-i", str(job.source), "-vn", "-c:a", "pcm_s16le"])
    if sample_rate is not None:
        command.extend(["-ar", str(sample_rate)])
    if channels is not None:
        command.extend(["-ac", str(channels)])
    command.append(str(job.target))

    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        return ConversionResult(job, ok=False, message=str(exc))

    if completed.returncode == 0:
        return ConversionResult(job, ok=True)

    if job.target.exists():
        job.target.unlink()
    message = completed.stderr.strip() or completed.stdout.strip() or "ffmpeg 转换失败"
    return ConversionResult(job, ok=False, message=message)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return parsed


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ogg2wav",
        description="使用 ffmpeg 批量把 OGG 音频转换成 WAV。",
    )
    parser.add_argument("input", type=Path, help="OGG 文件或包含 OGG 文件的目录")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="WAV 输出目录；默认在原 OGG 文件旁边生成同名 WAV",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="使用输出目录时不保留输入目录层级，全部平铺输出",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=positive_int,
        default=min(4, os.cpu_count() or 1),
        help="并发转换数量（默认：%(default)s）",
    )
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的 WAV 文件")
    parser.add_argument("--sample-rate", type=positive_int, help="目标采样率，例如 44100 或 48000")
    parser.add_argument("--channels", type=positive_int, choices=(1, 2), help="目标声道数：1 或 2")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg 可执行文件路径或命令名")
    parser.add_argument("--dry-run", action="store_true", help="只列出将转换的文件，不执行转换")
    return parser


def run(argv: Optional[Sequence[str]] = None) -> int:
    args = make_parser().parse_args(argv)
    input_path = args.input.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else None

    if shutil.which(args.ffmpeg) is None and not Path(args.ffmpeg).exists():
        print(f"错误：找不到 ffmpeg：{args.ffmpeg}", file=sys.stderr)
        return 2

    try:
        sources = find_ogg_files(input_path)
    except FileNotFoundError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if not sources:
        print(f"未找到 OGG 文件：{input_path}")
        return 0

    try:
        jobs = build_jobs(sources, input_path, output_dir, flat=args.flat)
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        for job in jobs:
            print(f"{job.source} -> {job.target}")
        print(f"共 {len(jobs)} 个文件")
        return 0

    results: List[ConversionResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [
            executor.submit(
                convert_one,
                job,
                ffmpeg=args.ffmpeg,
                overwrite=args.overwrite,
                sample_rate=args.sample_rate,
                channels=args.channels,
            )
            for job in jobs
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            status = "跳过" if result.skipped else "完成" if result.ok else "失败"
            print(f"[{status}] {result.job.source} -> {result.job.target}")

    succeeded = sum(1 for result in results if result.ok and not result.skipped)
    skipped = sum(1 for result in results if result.skipped)
    failures = [result for result in results if not result.ok]

    print(f"汇总：成功 {succeeded}，跳过 {skipped}，失败 {len(failures)}，共 {len(results)}")
    for failure in failures:
        print(f"失败原因：{failure.job.source}: {failure.message}", file=sys.stderr)
    return 1 if failures else 0


def main() -> int:
    return run()
