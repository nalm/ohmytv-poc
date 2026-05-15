"""카드뉴스 슬라이드 텍스트 → 1080×1080 PNG 이미지 변환."""

import re
from pathlib import Path

# 슬라이드별 배경 그라디언트 팔레트 (OhmyNews 레드 계열 + 보색)
GRADIENTS = [
    ("ee0000", "c20000"),  # 1 — 오마이뉴스 레드
    ("1a1a2e", "16213e"),  # 2 — 딥 네이비
    ("0f3460", "533483"),  # 3 — 블루-퍼플
    ("e94560", "0f3460"),  # 4 — 핑크-블루
    ("533483", "0f3460"),  # 5 — 퍼플-블루
    ("2d6a4f", "1b4332"),  # 6 — 딥 그린
    ("e76f51", "c45c3a"),  # 7 — 테라코타
    ("1a1a2e", "e94560"),  # 8 — 다크-핑크
    ("264653", "2a9d8f"),  # 9 — 틸
    ("6d4c41", "4e342e"),  # 10 — 브라운
]

SLIDE_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: 1080px; height: 1080px; overflow: hidden;
    font-family: 'Malgun Gothic', '맑은 고딕', 'Apple SD Gothic Neo', sans-serif;
    background: linear-gradient(135deg, #{grad_from}, #{grad_to});
    display: flex; flex-direction: column;
    justify-content: space-between;
    padding: 64px;
  }}
  .top {{
    display: flex; justify-content: space-between; align-items: center;
  }}
  .logo {{
    font-size: 28px; font-weight: 700; color: rgba(255,255,255,0.9);
    letter-spacing: 1px;
  }}
  .slide-num {{
    font-size: 26px; font-weight: 400; color: rgba(255,255,255,0.6);
    letter-spacing: 2px;
  }}
  .center {{
    flex: 1; display: flex; flex-direction: column;
    justify-content: center; gap: 36px;
    padding: 40px 0;
  }}
  .divider {{
    width: 60px; height: 4px;
    background: rgba(255,255,255,0.7);
    border-radius: 2px;
  }}
  .headline {{
    font-size: {headline_size}px; font-weight: 700;
    color: #ffffff; line-height: 1.4;
    word-break: keep-all; letter-spacing: -0.5px;
  }}
  .subtitle {{
    font-size: 34px; font-weight: 400;
    color: rgba(255,255,255,0.82);
    line-height: 1.55; word-break: keep-all;
  }}
  .bottom {{
    font-size: 24px; color: rgba(255,255,255,0.45);
    letter-spacing: 0.5px;
  }}
</style>
</head>
<body>
  <div class="top">
    <span class="logo">OhmyTV</span>
    <span class="slide-num">{slide_num} / {total}</span>
  </div>
  <div class="center">
    <div class="divider"></div>
    <div class="headline">{headline}</div>
    <div class="subtitle">{subtitle}</div>
  </div>
  <div class="bottom">오마이TV · ohmytv.com</div>
</body>
</html>
"""


def parse_slides(cardnews_md: str) -> list[dict]:
    """cardnews.md에서 슬라이드 목록 파싱."""
    slides = []
    blocks = re.split(r"(?=^## Slide \d+)", cardnews_md, flags=re.MULTILINE)
    for block in blocks:
        block = block.strip()
        if not block.startswith("## Slide"):
            continue
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        # 헤드라인: **텍스트**
        headline = ""
        subtitle = ""
        for line in lines[1:]:
            if line.startswith("**") and not headline:
                headline = line.strip("*").strip()
            elif not line.startswith("**") and not line.startswith("#") and not subtitle:
                subtitle = line
        if headline:
            slides.append({"headline": headline, "subtitle": subtitle})
    return slides


def _headline_fontsize(text: str) -> int:
    length = len(text)
    if length <= 14:
        return 66
    if length <= 22:
        return 54
    return 46


def generate_images(cardnews_md: str, output_dir: Path) -> list[Path]:
    """슬라이드 텍스트 → PNG 이미지 리스트 반환."""
    from playwright.sync_api import sync_playwright

    slides = parse_slides(cardnews_md)
    if not slides:
        raise ValueError("슬라이드를 파싱할 수 없습니다.")

    img_dir = output_dir / "cardnews_images"
    img_dir.mkdir(parents=True, exist_ok=True)

    total = len(slides)
    paths = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        page = browser.new_page(viewport={"width": 1080, "height": 1080})

        for i, slide in enumerate(slides):
            grad = GRADIENTS[i % len(GRADIENTS)]
            html = SLIDE_HTML.format(
                grad_from=grad[0],
                grad_to=grad[1],
                slide_num=i + 1,
                total=total,
                headline=slide["headline"],
                subtitle=slide["subtitle"],
                headline_size=_headline_fontsize(slide["headline"]),
            )
            page.set_content(html, wait_until="domcontentloaded")
            out = img_dir / f"slide_{i+1:02d}.png"
            page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1080, "height": 1080})
            paths.append(out)
            print(f"    slide {i+1}/{total} → {out.name}")

        browser.close()

    return paths
