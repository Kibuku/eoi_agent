from dotenv import load_dotenv
load_dotenv()
import os, json
keys = ['YOUR_EMAIL','SHEET_ID','ANTHROPIC_API_KEY','GMAIL_APP_PASSWORD','GOOGLE_SHEETS_CREDS']
print("env: all 5 loaded ✓" if all(os.environ.get(k) for k in keys) else "MISSING ENV")
creds_json = json.loads(os.environ['GOOGLE_SHEETS_CREDS'])
print(f"creds JSON parses ✓  service account: {creds_json['client_email']}")
from google.oauth2.service_account import Credentials
import gspread
creds = Credentials.from_service_account_info(creds_json, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(creds)
try:
    ws = gc.open_by_key(os.environ['SHEET_ID']).sheet1
    print(f"sheet access ✓  title='{ws.title}'  rows={ws.row_count}")
except Exception as e:
    print(f"SHEET ACCESS FAILED: {type(e).__name__}: {e}")
