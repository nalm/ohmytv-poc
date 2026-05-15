# ohmytv-poc

오마이TV 유튜브 영상 → 텍스트 기사 + 카드뉴스 자동 변환 파이프라인 (PoC)

## 빠른 시작

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY 입력

# 3. 실행
python pipeline.py run "https://www.youtube.com/watch?v=VIDEO_ID"
```

## 출력 파일

| 파일 | 내용 |
|------|------|
| `outputs/{video_id}/transcript.txt` | 원본 스크립트 |
| `outputs/{video_id}/article.md` | 기사 (700~1000자) |
| `outputs/{video_id}/cardnews.md` | 카드뉴스 슬라이드 8~10장 |
| `outputs/{video_id}/timing.json` | 단계별 소요시간 |
| `outputs/_timing_log.csv` | 누적 측정 로그 (PoC 평가용) |

## 옵션

```
python pipeline.py run URL [OPTIONS]

Options:
  --article-model TEXT     기사 생성 모델 [default: claude-sonnet-4-6]
  --cardnews-model TEXT    카드뉴스 생성 모델 [default: claude-haiku-4-5-20251001]
  --no-fallback            whisper fallback 비활성화
  --skip-cardnews          카드뉴스 생성 건너뜀
```

## 스크립트 추출 방식

1. **1차** — `youtube-transcript-api`: 한국어(`ko`) 자막이 있으면 바로 추출
2. **fallback** — `yt-dlp` 오디오 다운로드 → `faster-whisper` 전사
   - CPU 환경: `WHISPER_MODEL=medium` 권장 (`.env` 설정)
   - GPU 환경: `WHISPER_MODEL=large-v3`

## 제약사항

- 영상 길이 30분 초과 시 경고 출력 (PoC 범위 밖)
- 화자 분리 미지원 (대담형 영상은 스크립트 텍스트로만 추출)
- Anthropic API 외 유료 외부 서비스 미사용
