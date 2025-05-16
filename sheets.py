import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    try:
        creds_json = json.loads(os.environ["GOOGLE_CREDENTIALS"])
    except KeyError:
        raise RuntimeError("Environment variable 'GOOGLE_CREDENTIALS' not found.")

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)

    client = gspread.authorize(creds)

    try:
        sheet = client.open("Registrations").sheet1
    except Exception as e:
        raise RuntimeError(f"Failed to open the Google Sheet: {e}")

    return sheet
