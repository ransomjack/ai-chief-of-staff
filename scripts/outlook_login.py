"""One-time sign-in to your personal Outlook (outlook.com) account.

Run it in Azure Cloud Shell (or anywhere with Python):

    python3 scripts/outlook_login.py <MS_CLIENT_ID>

It prints a code. Open the link on your phone or laptop, sign in with your personal
Microsoft account and approve read-only access to calendar and mail. The script then
prints a refresh token. Put that token straight into Key Vault as the secret
ms-refresh-token. Do not paste it into chats, issues or files in the repo.
"""
import sys
import time

import requests

AUTH = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
SCOPES = "offline_access User.Read Calendars.Read Mail.Read"


def main(client_id: str) -> None:
    code = requests.post(f"{AUTH}/devicecode", data={"client_id": client_id, "scope": SCOPES}, timeout=20)
    code.raise_for_status()
    info = code.json()
    print(info["message"])
    deadline = time.time() + int(info.get("expires_in", 900))
    while time.time() < deadline:
        time.sleep(int(info.get("interval", 5)))
        resp = requests.post(f"{AUTH}/token", data={
            "client_id": client_id, "device_code": info["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}, timeout=20)
        data = resp.json()
        if "refresh_token" in data:
            print("\nSigned in. Store this as the Key Vault secret 'ms-refresh-token':\n")
            print(data["refresh_token"])
            return
        if data.get("error") not in ("authorization_pending", "slow_down"):
            sys.exit(f"Sign-in failed: {data.get('error_description', data)}")
    sys.exit("The code expired. Run the script again.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
