"""OhmyTV 영상 → 기사 + 카드뉴스 웹앱."""

import subprocess
import sys
import zipfile
import io
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv, find_dotenv

# Streamlit Cloud 환경에서 Playwright Chromium 자동 설치
@st.cache_resource(show_spinner="이미지 렌더러 준비 중...")
def _install_playwright():
    import os
    cache_dir = Path.home() / ".cache" / "ms-playwright"
    if cache_dir.exists() and list(cache_dir.glob("chromium-*/chrome-linux/chrome")):
        return True
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        st.error(
            "Playwright Chromium 설치 실패\n\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
        st.stop()
    return True

_install_playwright()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(find_dotenv(), override=True)

OUTPUTS_DIR = Path(__file__).parent / "outputs"

st.set_page_config(
    page_title="OhmyTV 기사·카드뉴스 변환기",
    page_icon="📺",
    layout="wide",
)

# ── 스타일 ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .title { font-size: 2rem; font-weight: 800; color: #EE0000; }
  .sub   { color: #666; font-size: 0.95rem; margin-bottom: 1.5rem; }
  .stat-box {
    background: #f8f8f8; border-radius: 10px;
    padding: 12px 20px; text-align: center;
  }
  .stat-label { font-size: 0.78rem; color: #888; }
  .stat-value { font-size: 1.5rem; font-weight: 700; color: #222; }
  .slide-counter {
    text-align: center; font-size: 0.9rem; color: #888; margin: 4px 0 8px;
  }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">📺 OhmyTV 기사·카드뉴스 변환기</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">유튜브 영상 URL을 입력하면 오마이뉴스 기사와 카드뉴스 이미지를 자동 생성합니다.</div>', unsafe_allow_html=True)

# ── URL 입력 ───────────────────────────────────────────────────────────────────
url = st.text_input(
    "YouTube URL",
    placeholder="https://www.youtube.com/watch?v=...",
    label_visibility="collapsed",
)
run_btn = st.button("변환 시작", type="primary", disabled=not url)

# ── 세션 상태 초기화 ────────────────────────────────────────────────────────────
for key in ("article_md", "img_paths", "timing", "video_title", "slide_idx", "error"):
    if key not in st.session_state:
        st.session_state[key] = None
if st.session_state.slide_idx is None:
    st.session_state.slide_idx = 0

# ── 파이프라인 실행 ────────────────────────────────────────────────────────────
if run_btn and url:
    st.session_state.slide_idx = 0
    st.session_state.error = None

    from modules.transcript import extract_video_id, get_transcript, get_video_title
    from modules.article import generate_article
    from modules.cardnews import generate_cardnews
    from modules.cardimage import generate_images
    import time

    try:
        video_id = extract_video_id(url)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    output_dir = OUTPUTS_DIR / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    timing = {}

    with st.status("변환 중...", expanded=True) as status:

        # 1. 스크립트
        st.write("📥 스크립트 추출 중...")
        t0 = time.time()
        transcript_result = get_transcript(url)
        timing["transcript"] = round(time.time() - t0, 1)
        text = transcript_result["text"]
        title = transcript_result.get("title") or get_video_title(url)
        (output_dir / "transcript.txt").write_text(text, encoding="utf-8")
        st.write(f"✅ 스크립트 완료 ({timing['transcript']}초 · {len(text):,}자)")

        # 2. 기사
        st.write("✍️ 기사 생성 중...")
        t0 = time.time()
        article_md = generate_article(text)
        timing["article"] = round(time.time() - t0, 1)
        header = f"<!-- source: {url} | title: {title} -->\n\n"
        (output_dir / "article.md").write_text(header + article_md, encoding="utf-8")
        st.write(f"✅ 기사 완료 ({timing['article']}초)")

        # 3. 카드뉴스 텍스트
        st.write("🃏 카드뉴스 텍스트 생성 중...")
        t0 = time.time()
        cardnews_md = generate_cardnews(text)
        timing["cardnews"] = round(time.time() - t0, 1)
        (output_dir / "cardnews.md").write_text(header + cardnews_md, encoding="utf-8")
        st.write(f"✅ 카드뉴스 텍스트 완료 ({timing['cardnews']}초)")

        # 4. 카드뉴스 이미지
        st.write("🖼️ 이미지 렌더링 중...")
        t0 = time.time()
        img_paths = generate_images(cardnews_md, output_dir)
        timing["cardimage"] = round(time.time() - t0, 1)
        st.write(f"✅ 이미지 완료 ({timing['cardimage']}초 · {len(img_paths)}장)")

        status.update(label="✅ 변환 완료!", state="complete", expanded=False)

    st.session_state.article_md  = article_md
    st.session_state.img_paths   = [str(p) for p in img_paths]
    st.session_state.timing      = timing
    st.session_state.video_title = title

# ── 결과 표시 ──────────────────────────────────────────────────────────────────
if st.session_state.article_md:
    total = sum(st.session_state.timing.values())

    # 타이밍 통계
    t = st.session_state.timing
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, label, val in [
        (c1, "스크립트", f"{t.get('transcript',0)}초"),
        (c2, "기사",     f"{t.get('article',0)}초"),
        (c3, "카드뉴스", f"{t.get('cardnews',0)}초"),
        (c4, "이미지",   f"{t.get('cardimage',0)}초"),
        (c5, "총계",     f"{total:.1f}초"),
    ]:
        col.markdown(
            f'<div class="stat-box"><div class="stat-label">{label}</div>'
            f'<div class="stat-value">{val}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # 본문 2열 레이아웃
    left, right = st.columns([6, 4], gap="large")

    # ── 기사 ──────────────────────────────────────────────────────────────────
    with left:
        st.subheader("📰 기사")
        st.markdown(st.session_state.article_md)
        st.download_button(
            "⬇ article.md 다운로드",
            data=st.session_state.article_md.encode("utf-8"),
            file_name="article.md",
            mime="text/markdown",
        )

    # ── 카드뉴스 슬라이드쇼 ──────────────────────────────────────────────────
    with right:
        st.subheader("🃏 카드뉴스")
        imgs = st.session_state.img_paths
        idx  = st.session_state.slide_idx

        st.markdown(
            f'<div class="slide-counter">{idx + 1} / {len(imgs)}</div>',
            unsafe_allow_html=True,
        )
        st.image(imgs[idx], use_container_width=True)

        prev_col, _, next_col = st.columns([1, 3, 1])
        with prev_col:
            if st.button("◀", disabled=(idx == 0), use_container_width=True):
                st.session_state.slide_idx -= 1
                st.rerun()
        with next_col:
            if st.button("▶", disabled=(idx == len(imgs) - 1), use_container_width=True):
                st.session_state.slide_idx += 1
                st.rerun()

        # ZIP 다운로드
        st.markdown("")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for p in imgs:
                zf.write(p, Path(p).name)
        st.download_button(
            "⬇ 이미지 전체 ZIP 다운로드",
            data=buf.getvalue(),
            file_name="cardnews_images.zip",
            mime="application/zip",
            use_container_width=True,
        )
