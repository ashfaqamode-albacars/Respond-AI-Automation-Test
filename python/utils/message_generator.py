import requests
from .config import load_config


def generate_message(prompt: str, car_data: dict = None) -> str:
    """
    Use OpenAI to generate a natural customer WhatsApp message from a prompt.

    Args:
        prompt: Instruction describing what the customer should say.
        car_data: Optional dict of car details to include in the message.

    Returns:
        A natural customer message string.
    """
    cfg = load_config()
    api_key = cfg.get("openai", {}).get("api_key")
    if not api_key:
        raise RuntimeError("No OpenAI API key configured. Cannot generate message.")

    system_prompt = (
        "You are simulating a customer sending a WhatsApp message to a used car dealership called Alba Cars in Dubai. "
        "Generate a short, natural WhatsApp message based on the instruction below. "
        "Write ONLY the message itself — no quotes, no explanation, no preamble. "
        "Keep it casual and realistic, like a real customer would type on WhatsApp."
    )

    user_prompt = f"Instruction: {prompt}"

    if car_data:
        # Build a readable summary of the car data
        car_parts = []
        for key in ["Year", "Brand", "Model", "Sub Model (Trim)", "Price", "Monthly Price", "Mileage", "SPEC", "Current Status"]:
            if key in car_data and car_data[key]:
                car_parts.append(f"{key}: {car_data[key]}")
        if car_parts:
            user_prompt += f"\n\nCar details to reference:\n" + "\n".join(car_parts)

    try:
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
                "max_tokens": 150,
                "temperature": 0.7,
            },
            timeout=15,
        )
        resp.raise_for_status()
        message = resp.json()["choices"][0]["message"]["content"].strip()
        # Remove quotes if the model wraps the message in them
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        return message

    except Exception as e:
        raise RuntimeError(f"Failed to generate customer message via OpenAI: {e}")
