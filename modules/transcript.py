import os
import re
import tempfile
from pathlib import Path
from typing import Optional

DURATION_WARN_SEC = 30 * 60  # 30분


def extract_video_id(url: str) -> str:
    for pat in [r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})"]:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    raise ValueError(f"YouTube video ID를 파싱할 수 없습니다: {url}")


def get_transcript(url: str, no_fallback: bool = False) -> dict:
    """
    Returns:
        {"text": str, "method": str, "duration_sec": int|None, "title": str}
    """
    video_id = extract_video_id(url)

    # 1차: yt-dlp 자막 다운로드 (youtube-transcript-api보다 안정적)
    result = _try_ytdlp_subtitle(url, video_id)
    if result:
        return result

    if no_fallback:
        raise RuntimeError("자막을 찾을 수 없고 --no-fallback 플래그가 설정되어 있습니다.")

    print("  자막 없음 - yt-dlp + whisper fallback 시작")
    return _fallback_whisper(url, video_id)


def _try_ytdlp_subtitle(url: str, video_id: str) -> Optional[dict]:
    try:
        import yt_dlp

        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                "writeautomaticsub": True,
                "writesubtitles": True,
                "subtitleslangs": ["ko"],
                "skip_download": True,
                "outtmpl": str(Path(tmpdir) / f"{video_id}.%(ext)s"),
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "")
                duration = info.get("duration")

            vtt_path = Path(tmpdir) / f"{video_id}.ko.vtt"
            if not vtt_path.exists():
                return None

            text = _parse_vtt(vtt_path.read_text(encoding="utf-8"))

        if not text.strip():
            return None

        if duration and duration > DURATION_WARN_SEC:
            print(f"  [WARNING] 영상 길이 {duration//60}분 - PoC 권장 범위(30분) 초과")

        return {"text": text, "method": "yt-dlp-subtitle", "duration_sec": duration, "title": title}

    except Exception as e:
        print(f"  yt-dlp 자막 추출 실패: {e}")
        return None


def _parse_vtt(vtt: str) -> str:
    """WebVTT에서 타임스탬프·메타·중복 제거 후 순수 텍스트 반환."""
    import html
    lines = vtt.splitlines()
    seen: set = set()
    texts = []
    for line in lines:
        line = line.strip()
        # 타임스탬프 행, WEBVTT/메타 헤더, 빈 줄, cue 번호 건너뜀
        if (not line or "-->" in line
                or re.match(r"^\d+$", line)
                or re.match(r"^(WEBVTT|Kind:|Language:)", line)):
            continue
        # HTML 태그 제거 (<c>, </c>, <00:00:00.000> 등) 후 엔티티 디코딩
        clean = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
        if clean and clean not in seen:
            seen.add(clean)
            texts.append(clean)
    return " ".join(texts)


def _fallback_whisper(url: str, video_id: str) -> dict:
    import yt_dlp
    from faster_whisper import WhisperModel

    whisper_model_name = os.getenv("WHISPER_MODEL", "medium")

    with tempfile.TemporaryDirectory() as tmpdir:
        print("  yt-dlp 오디오 다운로드 중...")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(Path(tmpdir) / f"{video_id}.%(ext)s"),
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "")
            duration = info.get("duration")
            ext = info.get("ext", "webm")

        audio_path = Path(tmpdir) / f"{video_id}.{ext}"

        if duration and duration > DURATION_WARN_SEC:
            print(f"  [WARNING] 영상 길이 {duration//60}분 - PoC 권장 범위(30분) 초과")

        print(f"  Whisper ({whisper_model_name}) 전사 중...")
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        method = f"whisper-{'gpu' if device == 'cuda' else 'cpu'}"

        model = WhisperModel(whisper_model_name, device=device, compute_type=compute_type)
        segments, _ = model.transcribe(str(audio_path), language="ko", beam_size=5)
        text = " ".join(seg.text for seg in segments).strip()

        return {"text": text, "method": method, "duration_sec": duration, "title": title}


def get_video_title(url: str) -> str:
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("title", "")
    except Exception:
        return ""
