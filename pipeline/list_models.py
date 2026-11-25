"""List the Gemini and Cloudflare image models this account can use (prints no secrets)."""
import os, requests
from dotenv import load_dotenv
load_dotenv(".env")
r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                 headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, params={"pageSize": 1000})
print("GEMINI:")
for m in r.json().get("models", []):
    if "flash" in m["name"] or "tts" in m["name"]:
        print(" ", m["name"].split("/")[1])
acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
r = requests.get(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/models/search",
                 headers={"Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"]},
                 params={"task": "Text-to-Image"})
print("CLOUDFLARE:")
for m in r.json().get("result", []):
    print(" ", m["name"])
