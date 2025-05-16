import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    try:
        creds_json_str = os.environ["GOOGLE_CREDENTIALS"]
        creds_json = json.loads(creds_json_str) if isinstance(creds_json_str, str) else creds_json_str
    except KeyError:
        raise RuntimeError("Environment variable 'GOOGLE_CREDENTIALS' not found.")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse GOOGLE_CREDENTIALS as JSON: {e}")

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)

    try:
        sheet = client.open("Registrations").sheet1
    except Exception as e:
        raise RuntimeError(f"Failed to open the Google Sheet: {e}")

    return sheet
