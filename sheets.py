import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_sheet():
    creds_json_str = os.environ.get("GOOGLE_CREDENTIALS")

    # Parse the string into a dictionary
    try:
        creds_json = json.loads(creds_json_str)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse GOOGLE_CREDENTIALS as JSON: {e}")

    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)

    # Open your spreadsheet
    return client.open("Registered_People.json").sheet1
