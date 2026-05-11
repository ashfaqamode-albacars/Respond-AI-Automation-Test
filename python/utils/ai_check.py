import requests
from .config import load_config

def ai_check_reply(actual_reply: str, expected_description: str) -> tuple[str, str]:
    """
    Use OpenAI to semantically check if the actual reply meets the expected outcome.
    
    Returns:
        (verdict, explanation)
        verdict: "SEMANTICALLY_PASS" or "SEMANTICALLY_FAIL"
        explanation: short explanation from the AI
    """
    cfg = load_config()
    api_key = cfg.get("openai", {}).get("api_key")
    if not api_key:
        return "AI_CHECK_SKIPPED", "No OpenAI API key configured"

    prompt = f"""You are a QA evaluator for an AI car sales agent called Alba.

A test was run where the expected outcome was:
"{expected_description}"

The AI agent replied with:
"{actual_reply}"

Does the AI agent's reply satisfy the expected outcome, even if it uses different wording?
Reply with exactly one of:
- SEMANTICALLY_PASS: [one sentence explaining why it passes]
- SEMANTICALLY_FAIL: [one sentence explaining why it fails]"""

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0,
            },
            timeout=15,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()

        if text.startswith("SEMANTICALLY_PASS"):
            return "SEMANTICALLY_PASS", text.replace("SEMANTICALLY_PASS:", "").strip()
        elif text.startswith("SEMANTICALLY_FAIL"):
            return "SEMANTICALLY_FAIL", text.replace("SEMANTICALLY_FAIL:", "").strip()
        else:
            return "AI_CHECK_UNCLEAR", text

    except Exception as e:
        return "AI_CHECK_ERROR", str(e)