# CareerShield for Gmail (Chrome MV3)

The extension adds a user-invoked CareerShield action to an opened Gmail
message. It uses CareerShield's existing authenticated analysis and history
endpoints; it does not scan inboxes or access attachment contents.

## Local setup

1. Start the CareerShield backend and frontend from the repository root:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
   ```

   In a second terminal:

   ```powershell
   cd frontend
   npm run dev -- --host 127.0.0.1
   ```

2. In Chrome, open `chrome://extensions/` and enable **Developer mode**.
3. Choose **Load unpacked** and select:
   `C:\CareerShield\extensions\careershield-gmail`
4. Copy the extension ID shown by Chrome. Add its exact origin to the root
   `.env` file:

   ```dotenv
   EXTENSION_ORIGINS=chrome-extension://YOUR_32_CHARACTER_EXTENSION_ID
   ```

   If more than one local extension origin needs access, separate the exact
   origins with commas. Do not use wildcard origins. Restart the backend after
   changing `.env`.
5. In CareerShield at `http://127.0.0.1:5173`, sign in and choose
   **Connect extension**. Copy the one-time pairing code.
6. Open the CareerShield extension popup. Under **Connection settings**, keep
   or enter:
   - API: `http://127.0.0.1:8000`
   - Website: `http://127.0.0.1:5173`

   Save the settings and approve Chrome's request to access that configured
   backend origin.
7. Paste the one-time pairing code into the popup and select **Connect
   securely**. Pairing codes expire after five minutes and are single-use.
8. Open [Gmail](https://mail.google.com/), then open an individual message.
   Click **Check with CareerShield** next to its subject. Open the extension
   popup, review the extracted subject, sender, body, links, and visible
   attachment metadata, and click **Analyze with CareerShield**. Alternatively,
   open the popup first and use **Select current email**.

The extension session is held in Chrome's session storage and is cleared when
Chrome closes. It expires on the same schedule as a CareerShield session. To
reconnect, sign in to the website and generate a new pairing code. **Sign out**
in the popup revokes that extension session.

## Privacy and security

- The Gmail content script runs only on `https://mail.google.com/`.
- A MutationObserver adds the action only when a single opened message is
  visible. It does not read email bodies or links while observing Gmail.
- The subject, sender, body, links, date, and visible attachment names are read
  only after the user clicks the injected action or the popup's **Select
  current email** control.
- The service worker only receives a content-free "email ready" notification
  for its toolbar badge; it does not receive or inspect email content.
- Extracted message data is held in `chrome.storage.session` for up to ten
  minutes to pass it to the popup. It is not written to persistent local
  storage, console output, or extension background messages. It is cleared on
  Chrome exit or when the user chooses **Check another email**.
- The Analyze action sends the selected message only to the API URL explicitly
  configured in the popup. Private-email analysis skips Hugging Face inference,
  live WHOIS/DNS, company search, recruiter verification, website probes, and
  local company-review lookup. Skipped checks remain unknown/unavailable and do
  not count as fraud evidence. The existing local model, scam indicators, and
  evidence-fusion pipeline are reused.
- After analysis, **View report & review optional checks** opens the
  authenticated CareerShield report. The extension itself never runs those
  checks. They remain off unless the user reviews the exact fields and gives
  per-analysis consent in the website; consent for one email does not apply to
  another.
- The session token is a short-lived bearer credential stored only in Chrome
  session storage. The password is never entered into or stored by the
  extension. Write requests include a CSRF token bound to the session.
- Email links are displayed as text, never opened by the extension.
- Attachment contents are not downloaded or analyzed. Use **Open CareerShield
  document upload** to download an attachment yourself and submit it through
  CareerShield's existing document workflow.
- CareerShield saves submitted analyses in the signed-in user's existing
  history. The current analysis record retains the full submitted email text
  in its job-description field and the sender address in its recruiter-email
  field; history can display the submitted text. This step does not change
  retention or delete historical records. Email analysis is preliminary
  decision support, not a definitive finding of fraud or a company reputation
  assessment.

## Tests

From the repository root, run:

```powershell
node --test extensions\careershield-gmail\tests\extension.test.cjs
.\.venv\Scripts\python.exe -m pytest backend\tests\test_auth.py backend\tests\test_documents.py -q
```

## Troubleshooting

- **Backend unavailable / CORS error:** verify the API URL, ensure the backend
  is running, and set `EXTENSION_ORIGINS` to the exact ID shown at
  `chrome://extensions/`; then restart the backend.
- **Pairing code rejected:** generate a fresh code from the signed-in website;
  each code expires after five minutes and is single-use.
- **No open email found:** navigate to an individual message in Gmail and try
  again. Gmail interface updates may require reloading its tab.
- **Session expired:** reconnect using a new one-time code from the website.
- **Cannot open a full report:** sign in to the CareerShield website in the
  browser using the same account that paired the extension.
