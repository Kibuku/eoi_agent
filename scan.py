import anthropic, json, os, time, smtplib, gspread
from datetime import date
from collections import deque
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

EMAIL    = os.environ["YOUR_EMAIL"]
SHEET_ID = os.environ["SHEET_ID"]

SYSTEM_PROMPT = """You are an EOI/tender research specialist for African development.
Search the web thoroughly. Return ONLY a JSON array of open opportunities.
Each item: title, platform, category, sector, country, deadline,
description, requirements, link, urgency (HIGH/MEDIUM/LOW).
HIGH = deadline within 7 days. MEDIUM = within 14 days. LOW = open/rolling.
Return ONLY valid JSON array, no markdown, no preamble."""

#Part 2: Queue processor
def scan_with_queue(platforms, context):
    client    = anthropic.Anthropic()
    today     = date.today().strftime("%B %d, %Y")
    queue     = deque(platforms)
    results   = []
    failed    = []
    processed = 0

    print(f"\n{'─'*50}")
    print(f"  EOI AGENT — QUEUE SCAN")
    print(f"  {len(queue)} platforms in queue | {today}")
    print(f"{'─'*50}\n")

    while queue:
        platform  = queue.popleft()
        processed += 1
        print(f"[{processed}/{processed + len(queue)}] Scanning: {platform}")
        try:
            batch = scan_single_platform(client, platform, context, today)
            results.extend(batch)
            print(f"  ✓ Found {len(batch)} opportunities\n")
        except Exception as e:
            print(f"  ✗ Failed: {e} — queued for retry\n")
            failed.append(platform)
        time.sleep(15)   # wait 15 seconds between platforms

    # ── RETRY PASS ────────────────────────────────────
    if failed:
        print(f"\n  RETRY PASS — {len(failed)} failed platforms\n")
        for platform in failed:
            print(f"  Retrying: {platform}")
            try:
                batch = scan_single_platform(client, platform, context, today)
                results.extend(batch)
                print(f"  ✓ Recovered — {len(batch)} opportunities\n")
            except Exception as e:
                print(f"  ✗ Permanently failed: {e}\n")
            time.sleep(15)  # wait 15 seconds between platforms

    # ── SUMMARY ───────────────────────────────────────
    high = sum(1 for r in results if r.get('urgency') == 'HIGH')
    med  = sum(1 for r in results if r.get('urgency') == 'MEDIUM')
    low  = sum(1 for r in results if r.get('urgency') == 'LOW')
    print(f"\n{'─'*50}")
    print(f"  SCAN COMPLETE")
    print(f"  Total : {len(results)} | HIGH: {high} | MED: {med} | LOW: {low}")
    print(f"{'─'*50}\n")
    return results

#Part 3: Single platform scan
def scan_single_platform(client, platform, context, today):
    signals  = "\n".join(f"- {s}" for s in context.get("priority_signals", []))
    sectors  = ", ".join(context.get("priority_sectors", []))
    keywords = ", ".join(context.get("boost_keywords", []))

    response = client.messages.create(
        model   = "claude-sonnet-4-6",
        max_tokens = 1000,
        system  = SYSTEM_PROMPT,
        tools   = [{"type": "web_search_20250305", "name": "web_search"}],
        messages = [{"role": "user", "content": f"""
            Search {platform} for open EOIs, tenders, RFPs, grants.
            Today: {today}. Find opportunities closing within 14 days or open/rolling.
            Priority themes:\n{signals}
            Sectors: {sectors}
            Keywords: {keywords}
            Countries: Kenya, Uganda, Tanzania, Ethiopia, Rwanda, Nigeria, Ghana.
            Return ONLY a JSON array. Empty array [] if nothing found.
        """}]
    )
    text = " ".join(b.text for b in response.content if b.type == "text")
    try:
        start, end = text.index("["), text.rindex("]")
        return json.loads(text[start:end+1])
    except:
        return []

#Part 4: Google Sheets writer
def update_sheet(new_eois):
    creds_json = json.loads(os.environ["GOOGLE_SHEETS_CREDS"])
    creds = Credentials.from_service_account_info(
        creds_json,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SHEET_ID).sheet1
    today_str = date.today().isoformat()

    for eoi in new_eois:
        ws.append_row([
            eoi.get("title",        ""),
            eoi.get("platform",     ""),
            eoi.get("category",     ""),
            eoi.get("sector",       ""),
            eoi.get("country",      ""),
            eoi.get("deadline",     ""),
            eoi.get("urgency",      ""),
            eoi.get("link",         ""),
            "PENDING",
            today_str,
            "",                           # Notes (you fill this)
            eoi.get("budget",       ""),  # enriched field
            eoi.get("eligibility",  ""),  # enriched field
            eoi.get("submission",   ""),  # enriched field
            eoi.get("contact",      ""),  # enriched field
        ])
    print(f"✓ Added {len(new_eois)} rows to Google Sheets")

#Part 5: Email digest
def send_email(new_eois):
    high = [e for e in new_eois if e.get("urgency") == "HIGH"]
    med  = [e for e in new_eois if e.get("urgency") == "MEDIUM"]
    low  = [e for e in new_eois if e.get("urgency") == "LOW"]

    html = f"""<html><body style='font-family:monospace;max-width:600px;margin:0 auto;padding:20px'>
    <h2 style='color:#c84b2f'>EOI Radar — {date.today().strftime('%d %b %Y')}</h2>
    <p style='color:#666'>{len(new_eois)} new opportunities ({len(high)} HIGH urgency)</p>
    <hr>"""

    for label, items, color in [
        ("🔴 HIGH URGENCY", high, "#c84b2f"),
        ("🟡 MEDIUM",       med,  "#c88e2f"),
        ("🟢 OPEN/ROLLING", low,  "#2a7a4a")
    ]:
        if not items: continue
        html += f'<h3 style="color:{color}">{label} ({len(items)})</h3>'
        for e in items:
            html += f"""<div style='border:1px solid #ddd;padding:14px;margin:10px 0'>
            <strong>{e.get('title','')}</strong><br>
            <span style='color:#888;font-size:12px'>{e.get('platform','')} · {e.get('country','')}</span><br>
            <span style='color:{color}'>Deadline: {e.get('deadline','Open')}</span><br>
            <p style='font-size:13px'>{e.get('description','')}</p>
            <a href='{e.get('link','#')}'>View Opportunity →</a>
            </div>"""
    html += "</body></html>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"EOI Radar: {len(new_eois)} new ({len(high)} urgent) — {date.today():%d %b %Y}"
    msg["From"] = EMAIL
    msg["To"]   = EMAIL
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL, os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(msg)
    print("✓ Email sent")


#Part 6: Deduplication and main
def load_seen():
    try:
        with open("seen_eois.json") as f: return set(json.load(f))
    except: return set()

def save_seen(seen):
    with open("seen_eois.json", "w") as f: json.dump(list(seen), f)

if __name__ == "__main__":
    with open("platforms.json") as f: platforms = json.load(f)
    with open("context.json")   as f: context   = json.load(f)

    seen     = load_seen()
    all_eois = scan_with_queue(platforms, context)
    new_eois = [e for e in all_eois if e.get("title") not in seen]

    print(f"Found {len(all_eois)} total, {len(new_eois)} new")

    if new_eois:
        update_sheet(new_eois)
        send_email(new_eois)
        seen.update(e["title"] for e in new_eois if "title" in e)
        save_seen(seen)
    else:
        print("No new EOIs this scan.")

# if __name__ == "__main__":
#     test_eois = [{
#         "title": "Test EOI - Solar Mini-grid Development Kenya",
#         "platform": "endev",
#         "category": "Grant",
#         "sector": "Solar Energy",
#         "country": "Kenya",
#         "deadline": "March 15, 2026",
#         "urgency": "HIGH",
#         "description": "This is a test opportunity to verify email and Sheets are working.",
#         "requirements": "Open to consulting firms in East Africa.",
#         "link": "https://endev.info/calls"
#     }]
#     update_sheet(test_eois)
#     send_email(test_eois)
