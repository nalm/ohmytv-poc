import csv
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class PipelineTiming:
    def __init__(self, video_url: str, video_id: str):
        self.video_url = video_url
        self.video_id = video_id
        self.video_title: str = ""
        self.video_duration_sec: Optional[int] = None
        self.stages: dict = {}
        self._pipeline_start = time.time()

    @contextmanager
    def stage(self, name: str, **extra):
        start_dt = datetime.now(timezone.utc)
        start_ts = time.time()
        print(f"  [{name}] 시작...")
        try:
            yield
        finally:
            end_dt = datetime.now(timezone.utc)
            duration = round(time.time() - start_ts, 2)
            self.stages[name] = {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "duration_sec": duration,
                **extra,
            }
            print(f"  [{name}] 완료 — {duration}초")

    def total_duration(self) -> float:
        return round(time.time() - self._pipeline_start, 2)

    def save(self, output_dir: Path, timing_log: Path) -> None:
        total = self.total_duration()
        data = {
            "video_url": self.video_url,
            "video_id": self.video_id,
            "video_title": self.video_title,
            "video_duration_sec": self.video_duration_sec,
            "stages": self.stages,
            "total_duration_sec": total,
        }

        timing_path = output_dir / "timing.json"
        timing_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  timing.json 저장 → {timing_path}")

        _append_csv(timing_log, data)
        print(f"  _timing_log.csv 기록 → {timing_log}")


def _append_csv(csv_path: Path, data: dict) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()

    stage_names = ["transcript", "article", "cardnews"]
    row = {
        "video_id": data["video_id"],
        "video_title": data["video_title"],
        "video_duration_sec": data["video_duration_sec"],
        "total_duration_sec": data["total_duration_sec"],
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
    for s in stage_names:
        info = data["stages"].get(s, {})
        row[f"{s}_sec"] = info.get("duration_sec", "")
        if s == "transcript":
            row["transcript_method"] = info.get("method", "")

    fieldnames = [
        "video_id", "video_title", "video_duration_sec",
        "transcript_sec", "transcript_method",
        "article_sec", "cardnews_sec",
        "total_duration_sec", "run_at",
    ]

    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
