(() => {
  const BUTTON_ID = 'careershield-gmail-check-button';
  const MAX_PENDING_AGE_MS = 10 * 60 * 1000;
  let scheduled = false;

  function isVisible(element) {
    if (!element || element.hidden) return false;
    const style = window.getComputedStyle(element);
    return style.display !== 'none' && style.visibility !== 'hidden';
  }

  function textWithoutQuotes(bodyNode) {
    const clone = bodyNode.cloneNode(true);
    clone.querySelectorAll(
      '.gmail_quote, .gmail_attr, .gmail_extra, blockquote, script, style, [aria-label="Quoted text"]',
    ).forEach((node) => node.remove());
    return CareerShieldEmailUtils.normalizeText(clone.innerText || clone.textContent);
  }

  function readAttachments(messageRoot) {
    return Array.from(messageRoot.querySelectorAll('.aQH'))
      .map((tile) => {
        const nameNode = tile.querySelector('.aV3, [data-tooltip]');
        const filename = nameNode?.getAttribute('data-tooltip')
          || nameNode?.innerText
          || tile.innerText;
        const extension = filename?.split('.').pop()?.toLowerCase();
        const mimeType = {
          pdf: 'application/pdf',
          doc: 'application/msword',
          docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          png: 'image/png',
          jpg: 'image/jpeg',
          jpeg: 'image/jpeg',
          webp: 'image/webp',
          txt: 'text/plain',
        }[extension] || 'Unknown';
        return { filename, mime_type: mimeType };
      })
      .filter((attachment) => attachment.filename);
  }

  function extractCurrentEmail() {
    if (!CareerShieldEmailUtils.isGmailUrl(window.location.href)) {
      throw new Error('Open Gmail to select a message.');
    }
    const main = document.querySelector('[role="main"]');
    const subjectNode = main?.querySelector('h2.hP');
    const bodyNodes = Array.from(main?.querySelectorAll('.a3s') || []).filter(isVisible);
    const bodyNode = bodyNodes.at(-1);
    if (!main || !subjectNode || !bodyNode) {
      throw new Error('Open an individual email before checking it.');
    }

    const messageRoot = bodyNode.closest('.adn') || bodyNode.parentElement || main;
    const senderNode = messageRoot.querySelector('.gD[email], [email][name], [email]');
    const senderEmail = senderNode?.getAttribute('email') || '';
    const senderName = senderNode?.getAttribute('name') || senderNode?.innerText || '';
    const dateNode = messageRoot.querySelector('.g3[title], [data-tooltip][title]');
    const bodyText = textWithoutQuotes(bodyNode);
    const links = Array.from(bodyNode.querySelectorAll('a[href]'))
      .map((anchor) => ({
        url: anchor.href || anchor.getAttribute('href'),
        label: anchor.innerText || anchor.textContent,
      }));

    const payload = {
      subject: subjectNode.innerText || subjectNode.textContent,
      sender_name: senderName,
      sender_email: senderEmail,
      body: bodyText,
      date: dateNode?.getAttribute('title') || '',
      links: CareerShieldEmailUtils.normalizeLinks(links),
      attachments: readAttachments(messageRoot),
    };
    CareerShieldEmailUtils.buildAnalysisRequest(payload);
    return payload;
  }

  async function saveSelectedEmail() {
    const email = extractCurrentEmail();
    await chrome.storage.session.set({
      pendingEmail: email,
      pendingEmailSavedAt: Date.now(),
    });
    chrome.runtime.sendMessage({ type: 'CAREERSHIELD_EMAIL_READY' });
    return email;
  }

  function showToast(message, isError = false) {
    document.getElementById('careershield-gmail-toast')?.remove();
    const toast = document.createElement('div');
    toast.id = 'careershield-gmail-toast';
    toast.setAttribute('role', 'status');
    toast.textContent = message;
    Object.assign(toast.style, {
      position: 'fixed',
      right: '24px',
      bottom: '24px',
      zIndex: '2147483647',
      maxWidth: '360px',
      padding: '12px 16px',
      borderRadius: '10px',
      color: '#ecfeff',
      background: isError ? '#7f1d1d' : '#0f2938',
      border: `1px solid ${isError ? '#fb7185' : '#22d3ee'}`,
      boxShadow: '0 12px 32px #0008',
      font: '13px/1.5 system-ui, sans-serif',
    });
    document.body.append(toast);
    window.setTimeout(() => toast.remove(), 6000);
  }

  function addCheckButton() {
    const main = document.querySelector('[role="main"]');
    const subjectNode = main?.querySelector('h2.hP');
    const hasOpenMessage = Array.from(main?.querySelectorAll('.a3s') || []).some(isVisible);
    if (!main || !subjectNode || !hasOpenMessage) {
      document.getElementById(BUTTON_ID)?.remove();
      return;
    }

    const target = subjectNode.parentElement;
    if (!target) return;
    const existing = document.querySelectorAll(`#${BUTTON_ID}`);
    existing.forEach((button, index) => {
      if (index > 0 || !target.contains(button)) button.remove();
    });
    if (target.querySelector(`#${BUTTON_ID}`)) return;

    const button = document.createElement('button');
    button.id = BUTTON_ID;
    button.type = 'button';
    button.setAttribute('aria-label', 'Check this opened email with CareerShield');
    button.title = 'Only reads this opened email after you click';
    button.textContent = '🛡 Check with CareerShield';
    Object.assign(button.style, {
      margin: '8px 0',
      padding: '7px 12px',
      border: '1px solid #0891b2',
      borderRadius: '7px',
      background: '#082f49',
      color: '#cffafe',
      cursor: 'pointer',
      font: '500 12px system-ui, sans-serif',
    });
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.textContent = 'Preparing selected email…';
      try {
        await saveSelectedEmail();
        button.textContent = 'Email ready · open CareerShield';
        showToast('Email extracted only after your click. Open the CareerShield extension to review and analyze it.');
      } catch (error) {
        button.textContent = '🛡 Check with CareerShield';
        showToast(error.message || 'Could not read this email. Open a message and try again.', true);
      } finally {
        button.disabled = false;
      }
    });
    target.append(button);
  }

  function scheduleButtonUpdate() {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(() => {
      scheduled = false;
      addCheckButton();
    }, 200);
  }

  if (CareerShieldEmailUtils.isGmailUrl(window.location.href)) {
    const observer = new MutationObserver(scheduleButtonUpdate);
    observer.observe(document.documentElement, { childList: true, subtree: true });
    scheduleButtonUpdate();
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== 'CAREERSHIELD_EXTRACT_CURRENT_EMAIL') return false;
    saveSelectedEmail()
      .then((email) => sendResponse({ ok: true, email }))
      .catch((error) => sendResponse({
        ok: false,
        error: error.message || 'Could not extract the opened email.',
      }));
    return true;
  });

  chrome.storage.session.get(['pendingEmailSavedAt']).then(({ pendingEmailSavedAt }) => {
    if (pendingEmailSavedAt && Date.now() - pendingEmailSavedAt > MAX_PENDING_AGE_MS) {
      chrome.storage.session.remove(['pendingEmail', 'pendingEmailSavedAt']);
    }
  });
})();
