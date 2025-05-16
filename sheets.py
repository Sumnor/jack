import os
import json
from oauth2client.service_account import ServiceAccountCredentials
import gspread

def get_sheet():
    try:
        creds_json_str = os.environ["GOOGLE_CREDENTIALS"]

        # Safely load the JSON string
        creds_json = json.loads(creds_json_str) if isinstance(creds_json_str, str) else creds_json_str

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)

        # Open your sheet here
        return client.open("Your-Sheet-Name").sheet1

    except KeyError:
        raise RuntimeError("Environment variable 'GOOGLE_CREDENTIALS' not found.")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse GOOGLE_CREDENTIALS as JSON: {e}")
