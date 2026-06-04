"""
video_finalizer.py — Наложение текста на видео через FFmpeg drawtext
"""

import subprocess
import os


def add_text_overlay(
input_video: str,
output_path: str,
text: str,
font_size: int = 28,
font_color: str = "white",
box_color: str = "black@0.5",
position: str = "bottom"
) -> bool:
"""
Накладывает текст на видео через FFmpeg drawtext.

position: "bottom" — внизу, "top" — вверху, "center" — по центру
"""
safe_text = text.replace("'", "'\\\\\\''").replace(":", "\\:").replace(",", "\\,")

if position == "bottom":
    y_pos = "h-th-40"
elif position == "top":
    y_pos = "40"
else:
    y_pos = "(h-th)/2"

filter_str = (
    f"drawtext=text='{safe_text}':"
    f"fontsize={font_size}:"
    f"fontcolor={font_color}:"
    f"box=1:boxcolor={box_color}:"
    f"boxborderw=8:"
    f"x=(w-text_w)/2:"
    f"y={y_pos}:"
    f"enable='between(t,0,9999)'"
)

cmd = [
    "ffmpeg", "-y",
    "-i", input_video,
    "-vf", filter_str,
    "-c:a", "copy",
    "-preset", "fast",
    output_path
]

result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode == 0:
    print(f"[VideoFinalizer] Текст наложен: {os.path.basename(output_path)}")
else:
    print(f"[VideoFinalizer] Ошибка: {result.stderr[:200]}")

return result.returncode == 0


def batch_add_text(
video_dir: str,
texts: list,
output_dir: str = "output/final",
**kwargs
) -> list:
"""
Для каждого видео из video_dir берёт соответствующий текст
и накладывает его. videos сортируются, texts — по порядку.
"""
os.makedirs(output_dir, exist_ok=True)

videos = sorted([f for f in os.listdir(video_dir) if f.endswith(".mp4")])
if not videos:
    print("[VideoFinalizer] Нет видео для обработки")
    return []

print(f"[VideoFinalizer] Обработка {min(len(videos), len(texts))} видео...")

final_paths = []
for i, video_name in enumerate(videos):
    if i >= len(texts):
        print(f"[VideoFinalizer] Закончились тексты на видео #{i+1}")
        break

    input_path = os.path.join(video_dir, video_name)
    output_path = os.path.join(output_dir, f"final_{i+1:04d}.mp4")

    success = add_text_overlay(input_path, output_path, texts[i], **kwargs)
    if success:
        final_paths.append(output_path)

print(f"[VideoFinalizer] Готово: {len(final_paths)} видео")
return final_paths


if __name__ == "__main__":
texts = ["Смотрите это видео! #тренд #лайфхак", "Невероятно, но факт! #shorts #рекомендации"]
batch_add_text("output/clips", texts)