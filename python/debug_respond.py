import requests
import yaml

with open("config/config.yaml") as f:
    cfg = yaml.safe_load(f)

headers = {
    "Authorization": f"Bearer {cfg['respond']['api_key']}",
    "Content-Type": "application/json"
}

# Try correct base URL
contact_id = +971504450876

resp = requests.get(
    f"https://api.respond.io/v2/contact/phone:{contact_id}/message/list",
    headers=headers,
    # params={"limit": 5}
)
print("Status:", resp.status_code)
print("Response:", resp.text)