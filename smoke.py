from dotenv import load_dotenv
load_dotenv()
import json, scan
with open("context.json") as f: context = json.load(f)
client = scan.anthropic.Anthropic()
from datetime import date
print("Running scan against 1 platform: endev...")
results = scan.scan_single_platform(client, "endev (endev.info/calls)", context, date.today().strftime("%B %d, %Y"))
print(f"Got {len(results)} results")
for r in results[:3]:
    print(f"  - [{r.get('urgency','?')}] {r.get('title','?')} | {r.get('deadline','?')}")
print("\nWriting to sheet...")
if results:
    scan.update_sheet(results[:2])  # write at most 2 rows so we don't spam
print("Sending test email...")
if results:
    scan.send_email(results[:2])
print("✓ smoke test complete")
