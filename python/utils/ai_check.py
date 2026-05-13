import json
import requests
from .config import load_config


def ai_check_reply(actual_reply: str, expected_description: str) -> dict:
    """
    Use OpenAI Structured Outputs to semantically evaluate the agent reply.

    Returns a dict:
      {
        "pass_fail": "PASS" | "FAIL",
        "confidence": float,  # 0.0 to 1.0
        "notes": str
      }
    """
    cfg = load_config()
    api_key = cfg.get("openai", {}).get("api_key")
    if not api_key:
        return {
            "pass_fail": "FAIL",
            "confidence": 0.0,
            "notes": "AI_CHECK_SKIPPED: No OpenAI API key configured",
        }

    try:
        system_prompt = (
            "You are a strict QA evaluator for Alba's AI agent responses. "
            "Judge semantic alignment with expected outcome, not literal keyword overlap."
        )
        user_prompt = (
            f"Expected outcome:\n{expected_description}\n\n"
            f"Actual AI reply:\n{actual_reply}\n\n"
            "Determine whether the reply semantically satisfies the expected outcome."
        )

        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "semantic_reply_evaluation",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "pass_fail": {
                                    "type": "string",
                                    "enum": ["PASS", "FAIL"],
                                },
                                "confidence": {
                                    "type": "number",
                                    "minimum": 0,
                                    "maximum": 1,
                                },
                                "notes": {"type": "string"},
                            },
                            "required": ["pass_fail", "confidence", "notes"],
                            "additionalProperties": False,
                        },
                    },
                },
                "temperature": 0,
            },
            timeout=15,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        pass_fail = parsed.get("pass_fail", "FAIL")
        confidence = float(parsed.get("confidence", 0.0))
        notes = str(parsed.get("notes", "")).strip()

        if pass_fail not in ("PASS", "FAIL"):
            pass_fail = "FAIL"
        if confidence < 0:
            confidence = 0.0
        if confidence > 1:
            confidence = 1.0
        if not notes:
            notes = "No notes returned by evaluator."

        return {
            "pass_fail": pass_fail,
            "confidence": confidence,
            "notes": notes,
        }

    except Exception as e:
        return {
            "pass_fail": "FAIL",
            "confidence": 0.0,
            "notes": f"AI_CHECK_ERROR: {e}",
        }