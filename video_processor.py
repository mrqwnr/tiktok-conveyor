"""
video_processor.py — FFmpeg нарезка длинного видео на короткие клипы
"""

import subprocess
import random
import os
from pathlib import Path


def get_video_duration(video_path: str) -> float:
    """Получить длительность видео в секундах через FFprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def random_cut_params(duration: float, clip_min: int = 15, clip_max: int = 30) -> tuple:
    """
    Случайная точка старта и длина для нарезки.
    Возвращает (start_time, clip_duration).
    """
    max_duration = min(clip_max, duration - 1)
    if max_duration < clip_min:
        return None  # видео слишком короткое

    clip_duration = random.randint(clip_min, max_duration)
    max_start = duration - clip_duration
    start_time = random.uniform(0, max_start)
    return (start_time, clip_duration)


def cut_clip(
    input_path: str,
    output_path: str,
    start_time: float,
    duration: float,
    fps: int = 30
) -> bool:
    """
    Нарезать кусок видео.
    """
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-i", input_path,
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-r", str(fps),
        "-an",  # без аудио
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def generate_clips(
    input_path: str,
    output_dir: str,
    num_clips: int = 100,
    clip_min: int = 15,
    clip_max: int = 30,
    prefix: str = "clip"
) -> list:
    """
    Главная функция — нарезает N случайных клипов из исходного видео.
    Возвращает список путей к готовым клипам.
    """
    os.makedirs(output_dir, exist_ok=True)

    duration = get_video_duration(input_path)
    print(f"[VideoProcessor] Исходное видео: {duration:.1f} сек")

    if duration < clip_min:
        print(f"[VideoProcessor] Ошибка: видео слишком короткое ({duration:.1f} сек)")
        return []

    generated = []
    attempts = 0
    max_attempts = num_clips * 3  # чтобы не зависнуть

    while len(generated) < num_clips and attempts < max_attempts:
        attempts += 1
        params = random_cut_params(duration, clip_min, clip_max)
        if params is None:
            break
        
        start_time, clip_dur = params
        output_path = os.path.join(output_dir, f"{prefix}_{len(generated)+1:04d}.mp4")
        
        if cut_clip(input_path, output_path, start_time, clip_dur):
            generated.append(output_path)
            print(f"[VideoProcessor] Клип #{len(generated)}: {start_time:.1f}с -> +{clip_dur:.0f}с")

    print(f"[VideoProcessor] Готово: {len(generated)} клипов")
    return generated


if __name__ == "__main__":
    # Тест
    clips = generate_clips("input/demo.mp4", "output/clips", num_clips=10)
    for c in clips:
        print(c)