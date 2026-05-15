#!/usr/bin/env python3
"""오마이TV 영상 → 기사 + 카드뉴스 변환 파이프라인."""

import sys
from pathlib import Path

import typer
from dotenv import load_dotenv, find_dotenv

# Windows cp949 환경에서 한글/특수문자 출력 보장
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv(find_dotenv(), override=True)

app = typer.Typer(help="오마이TV 영상 → 기사/카드뉴스 변환 CLI", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

OUTPUTS_DIR = Path(__file__).parent / "outputs"


@app.command()
def run(
    url: str = typer.Argument(..., help="YouTube 영상 URL"),
    article_model: str = typer.Option("claude-sonnet-4-6", help="기사 생성 모델"),
    cardnews_model: str = typer.Option("claude-haiku-4-5-20251001", help="카드뉴스 생성 모델"),
    no_fallback: bool = typer.Option(False, "--no-fallback", help="whisper fallback 비활성화"),
    skip_cardnews: bool = typer.Option(False, "--skip-cardnews", help="카드뉴스 생성 건너뜀"),
):
    """YouTube URL 하나를 입력받아 스크립트·기사·카드뉴스를 생성합니다."""
    from modules.transcript import extract_video_id, get_transcript, get_video_title
    from modules.article import generate_article
    from modules.cardnews import generate_cardnews
    from modules.timing import PipelineTiming

    video_id = extract_video_id(url)
    output_dir = OUTPUTS_DIR / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    timing_log = OUTPUTS_DIR / "_timing_log.csv"

    timing = PipelineTiming(video_url=url, video_id=video_id)

    typer.echo(f"\n▶ 영상 ID: {video_id}")
    typer.echo(f"  출력 폴더: {output_dir}\n")

    # ── 1. 스크립트 추출 ──────────────────────────────────────────────────────
    transcript_result: dict = {}
    with timing.stage("transcript"):
        transcript_result = get_transcript(url, no_fallback=no_fallback)
    timing.stages["transcript"]["method"] = transcript_result["method"]

    text = transcript_result["text"]
    (output_dir / "transcript.txt").write_text(text, encoding="utf-8")

    # 영상 제목 보완 (transcript-api는 title을 못 가져오는 경우 있음)
    title = transcript_result.get("title") or get_video_title(url)
    timing.video_title = title
    timing.video_duration_sec = transcript_result.get("duration_sec")

    typer.echo(f"  제목: {title}")
    typer.echo(f"  스크립트 길이: {len(text):,}자  방법: {transcript_result['method']}\n")

    # ── 2. 기사 생성 ──────────────────────────────────────────────────────────
    with timing.stage("article"):
        article_md = generate_article(text, model=article_model)

    # 기사 상단에 원본 영상 메타 주석 추가
    article_header = f"<!-- source: {url} | title: {title} -->\n\n"
    (output_dir / "article.md").write_text(article_header + article_md, encoding="utf-8")
    typer.echo(f"  기사 저장 → {output_dir / 'article.md'}\n")

    # ── 3. 카드뉴스 생성 ─────────────────────────────────────────────────────
    if not skip_cardnews:
        with timing.stage("cardnews"):
            cardnews_md = generate_cardnews(text, model=cardnews_model)

        cardnews_header = f"<!-- source: {url} | title: {title} -->\n\n"
        cardnews_path = output_dir / "cardnews.md"
        cardnews_path.write_text(cardnews_header + cardnews_md, encoding="utf-8")
        typer.echo(f"  카드뉴스 저장 → {cardnews_path}\n")

        # ── 3b. 카드뉴스 이미지 생성 ────────────────────────────────────────
        from modules.cardimage import generate_images
        typer.echo("  [cardimage] 이미지 렌더링 중...")
        with timing.stage("cardimage"):
            img_paths = generate_images(cardnews_md, output_dir)
        typer.echo(f"  카드뉴스 이미지 {len(img_paths)}장 → {output_dir / 'cardnews_images'}\n")

    # ── 4. 타이밍 저장 ───────────────────────────────────────────────────────
    timing.save(output_dir, timing_log)

    typer.echo(f"\n✓ 완료  총 소요시간: {timing.total_duration()}초")
    typer.echo(f"  출력: {output_dir}")


if __name__ == "__main__":
    app()
