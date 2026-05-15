from pathlib import Path

import anthropic

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def generate_cardnews(transcript: str, model: str = "claude-haiku-4-5-20251001") -> str:
    system_prompt = (PROMPTS_DIR / "cardnews_system.md").read_text(encoding="utf-8")

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"다음 영상 스크립트를 바탕으로 카드뉴스 슬라이드 텍스트를 작성해줘.\n\n---\n{transcript}\n---",
            }
        ],
    )
    return message.content[0].text
