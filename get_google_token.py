"""
Script OAuth2 - A executer UNE SEULE FOIS pour obtenir le refresh_token.
Usage: python get_google_token.py
"""

import json, os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]
CREDENTIALS_FILE = "credentials.json"

def main():
    print("=" * 55)
    print("  Obtention du Refresh Token Google OAuth2")
    print("  Cabinet Dr. Khiri")
    print("=" * 55, "\n")

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERREUR: '{CREDENTIALS_FILE}' introuvable!")
        print(f"Placez le fichier dans: {os.getcwd()}")
        return

    print(f"OK: {CREDENTIALS_FILE} trouve")
    print("Ouverture du navigateur...\n")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=8090, prompt="consent", access_type="offline")

    with open("token.json", "w") as f:
        json.dump({
            "token": creds.token, "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri, "client_id": creds.client_id,
            "client_secret": creds.client_secret,
        }, f, indent=2)

    with open(CREDENTIALS_FILE) as f:
        cred_data = json.load(f)
    info = cred_data.get("web", cred_data.get("installed", {}))

    print("\n" + "=" * 55)
    print("  AUTHENTIFICATION REUSSIE !")
    print("=" * 55)
    print("\nCopiez ces valeurs dans votre fichier .env :")
    print("-" * 55)
    print(f"GOOGLE_CLIENT_ID={info.get('client_id', 'N/A')}")
    print(f"GOOGLE_CLIENT_SECRET={info.get('client_secret', 'N/A')}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print("-" * 55)
    print("\nLancez ensuite : uvicorn main:app --reload")

if __name__ == "__main__":
    main()
