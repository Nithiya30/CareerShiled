(() => {
  const DEFAULT_SETTINGS = {
    backendUrl: 'http://127.0.0.1:8000',
    webUrl: 'http://127.0.0.1:5173',
  };
  const SESSION_KEYS = ['accessToken', 'csrfToken', 'account', 'pendingEmail', 'pendingEmailSavedAt'];
  const $ = (id) => document.getElementById(id);
  let settings = { ...DEFAULT_SETTINGS };
  let auth = null;
  let pendingEmail = null;
  let latestResult = null;
  let noticeTimer = 0;

  function showNotice(message, isError = false) {
    const notice = $('notice');
    notice.textContent = message;
    notice.classList.toggle('error', isError);
    notice.hidden = false;
    window.clearTimeout(noticeTimer);
    noticeTimer = window.setTimeout(() => { notice.hidden = true; }, 7000);
  }

  function setStatus(id, message, good = false) {
    $(`${id}-status`).textContent = message;
    $(`${id}-indicator`).className = `indicator ${good ? 'good' : 'bad'}`;
  }

  function normalizedOrigin(value) {
    const url = new URL(value);
    if (url.username || url.password || url.search || url.hash || url.pathname !== '/') {
      throw new Error('Use an origin only, without credentials, path, query, or fragment.');
    }
    const localHosts = new Set(['localhost', '127.0.0.1', '[::1]']);
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && localHosts.has(url.hostname))) {
      throw new Error('Use HTTPS for remote servers. HTTP is allowed only for localhost.');
    }
    return url.origin;
  }

  async function loadSettings() {
    const saved = await chrome.storage.local.get(['backendUrl', 'webUrl']);
    settings = { ...DEFAULT_SETTINGS, ...saved };
    $('backend-url').value = settings.backendUrl;
    $('web-url').value = settings.webUrl;
  }

  async function requestApi(path, { method = 'GET', body, token, csrfToken, timeoutMs = 8000 } = {}) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
    const headers = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (token) headers.Authorization = `Bearer ${token}`;
    if (csrfToken) headers['X-CSRF-Token'] = csrfToken;

    try {
      const response = await fetch(`${settings.backendUrl}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: 'omit',
        cache: 'no-store',
        signal: controller.signal,
      });
      let data = {};
      try {
        data = await response.json();
      } catch {
        throw new Error('CareerShield returned an unreadable response.');
      }
      if (!response.ok) {
        const error = new Error(
          typeof data.detail === 'string'
            ? data.detail
            : `CareerShield request failed (HTTP ${response.status}).`,
        );
        error.status = response.status;
        throw error;
      }
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('CareerShield did not respond in time.');
      if (error instanceof TypeError) {
        throw new Error('Could not reach CareerShield. Check the backend URL and CORS extension-origin setting.');
      }
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  async function loadAuth() {
    const stored = await chrome.storage.session.get(SESSION_KEYS);
    if (!stored.accessToken || !stored.csrfToken) {
      auth = null;
      return;
    }
    try {
      const user = await requestApi('/api/auth/me', { token: stored.accessToken });
      auth = {
        accessToken: stored.accessToken,
        csrfToken: stored.csrfToken,
        user,
      };
      await chrome.storage.session.set({ account: user });
    } catch (error) {
      if (error.status === 401) {
        await chrome.storage.session.remove(['accessToken', 'csrfToken', 'account']);
        auth = null;
        showNotice('Your extension session expired. Connect again from the signed-in CareerShield website.', true);
        return;
      }
      throw error;
    }
  }

  async function checkBackend() {
    try {
      const health = await requestApi('/api/health');
      if (health.status !== 'ok') throw new Error('CareerShield reported an unhealthy status.');
      setStatus('backend', `Backend online · database ${health.database || 'status unknown'}`, true);
    } catch (error) {
      setStatus('backend', 'Backend unavailable');
      showNotice(error.message, true);
    }
  }

  function renderAuth() {
    $('pairing-panel').hidden = Boolean(auth);
    $('account-panel').hidden = !auth;
    if (auth) $('account-email').textContent = auth.user.email;
    $('auth-status').textContent = auth ? `Signed in · ${auth.user.email}` : 'Not connected';
    $('auth-indicator').className = `indicator ${auth ? 'good' : ''}`;
  }

  function renderEmail(email) {
    pendingEmail = email || null;
    $('email-panel').hidden = !pendingEmail;
    if (!pendingEmail) return;

    $('email-subject').textContent = pendingEmail.subject || '(Subject unavailable)';
    $('email-sender').textContent = `${pendingEmail.sender_name || 'Sender'} <${pendingEmail.sender_email || 'address unavailable'}>`;
    $('email-date').textContent = pendingEmail.date || '';
    $('email-preview').textContent = pendingEmail.body || '';
    $('analyze-email').disabled = !auth;

    const links = pendingEmail.links || [];
    $('email-links-section').hidden = links.length === 0;
    $('email-links').replaceChildren(...links.map(({ url }) => {
      const item = document.createElement('li');
      item.textContent = url;
      return item;
    }));

    const attachments = pendingEmail.attachments || [];
    $('email-attachments-section').hidden = attachments.length === 0;
    $('email-attachments').replaceChildren(...attachments.map((attachment) => {
      const item = document.createElement('li');
      item.textContent = `${attachment.filename} · ${attachment.mime_type || 'type unavailable'} · contents not read`;
      return item;
    }));
  }

  function renderEvidence(sectionId, listId, values, warning = false) {
    $(sectionId).hidden = !values.length;
    $(listId).replaceChildren(...values.slice(0, 8).map((value) => {
      const item = document.createElement('li');
      item.textContent = value;
      if (warning) item.className = 'warning';
      return item;
    }));
  }

  function renderResult(result) {
    latestResult = result;
    $('result-panel').hidden = false;
    $('trust-score').textContent = Number.isFinite(result.trust_score)
      ? `${Math.round(result.trust_score)}/100`
      : 'Unavailable';
    $('risk-level').textContent = result.risk_level || 'Needs verification';
    const risk = (result.risk_level || '').toLowerCase();
    const riskClass = risk.includes('fraud')
      ? 'high'
      : risk.includes('verification') || risk.includes('uncertain')
        ? 'medium'
        : risk.includes('legitimate')
          ? 'low'
          : '';
    $('risk-level').className = `risk-badge ${riskClass}`.trim();
    const confidence = Number(result.confidence);
    $('confidence').textContent = Number.isFinite(confidence)
      ? `Confidence: ${Math.round(confidence * 100)}%`
      : 'Confidence unavailable';
    renderEvidence('warning-section', 'warning-list', result.negative_evidence || [], true);
    renderEvidence('positive-section', 'positive-list', result.positive_evidence || []);
    renderEvidence('unknown-section', 'unknown-list', result.unknown_evidence || []);
    const domainResult = result.domain_result || {};
    const domainObservations = [
      domainResult.status ? `Status: ${domainResult.status}` : '',
      domainResult.explanation || '',
      ...(domainResult.signals || []),
    ].filter(Boolean);
    $('domain-section').hidden = domainObservations.length === 0;
    $('domain-observations').textContent = domainObservations.join(' ');
  }

  async function saveConnectionSettings() {
    const saveButton = $('save-settings');
    saveButton.disabled = true;
    try {
      const backendUrl = normalizedOrigin($('backend-url').value.trim());
      const webUrl = normalizedOrigin($('web-url').value.trim());
      const permissionPattern = `${new URL(backendUrl).origin}/*`;
      const granted = await chrome.permissions.request({ origins: [permissionPattern] });
      if (!granted) throw new Error('Browser permission for the configured backend was not granted.');
      await chrome.storage.local.set({ backendUrl, webUrl });
      settings = { backendUrl, webUrl };
      showNotice('Connection settings saved.');
      await checkBackend();
      await loadAuth();
      renderAuth();
    } catch (error) {
      showNotice(error.message || 'Could not save connection settings.', true);
    } finally {
      saveButton.disabled = false;
    }
  }

  async function pairAccount() {
    const button = $('pair-button');
    button.disabled = true;
    try {
      const code = $('pairing-code').value.trim();
      if (code.length < 20) throw new Error('Paste the complete one-time pairing code from CareerShield.');
      const response = await requestApi('/api/auth/extension/exchange', {
        method: 'POST',
        body: { code },
        timeoutMs: 12000,
      });
      if (!response.access_token || !response.csrf_token || !response.user?.email) {
        throw new Error('CareerShield returned an incomplete sign-in response.');
      }
      auth = {
        accessToken: response.access_token,
        csrfToken: response.csrf_token,
        user: response.user,
      };
      await chrome.storage.session.set({
        accessToken: auth.accessToken,
        csrfToken: auth.csrfToken,
        account: auth.user,
      });
      $('pairing-code').value = '';
      renderAuth();
      showNotice('Extension connected. Your session is kept only until Chrome closes.');
    } catch (error) {
      showNotice(error.message || 'Could not connect the extension.', true);
    } finally {
      button.disabled = false;
    }
  }

  async function signOut() {
    if (!auth) return;
    try {
      await requestApi('/api/auth/logout', {
        method: 'POST',
        token: auth.accessToken,
        csrfToken: auth.csrfToken,
      });
      showNotice('Extension session signed out.');
    } catch (error) {
      showNotice(error.status === 401 ? 'Extension session already expired.' : error.message, error.status !== 401);
    } finally {
      auth = null;
      await chrome.storage.session.remove(['accessToken', 'csrfToken', 'account']);
      renderAuth();
    }
  }

  async function extractCurrentEmail() {
    const button = $('extract-email');
    button.disabled = true;
    button.textContent = 'Reading selected message…';
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id || !CareerShieldEmailUtils.isGmailUrl(tab.url || '')) {
        throw new Error('Open Gmail and select one email before extracting it.');
      }
      const response = await chrome.tabs.sendMessage(tab.id, {
        type: 'CAREERSHIELD_EXTRACT_CURRENT_EMAIL',
      });
      if (!response?.ok || !response.email) {
        throw new Error(response?.error || 'No readable email was returned.');
      }
      await chrome.storage.session.set({
        pendingEmail: response.email,
        pendingEmailSavedAt: Date.now(),
      });
      renderEmail(response.email);
      $('result-panel').hidden = true;
      showNotice('Email extracted. Review it, then choose Analyze with CareerShield.');
    } catch (error) {
      showNotice(error.message || 'Could not extract the current email.', true);
    } finally {
      button.disabled = false;
      button.textContent = 'Select current email';
    }
  }

  async function analyzeEmail() {
    if (!auth || !pendingEmail) {
      showNotice('Connect your account and select a readable email first.', true);
      return;
    }
    const button = $('analyze-email');
    button.disabled = true;
    button.textContent = 'Analyzing recruitment signals…';
    $('result-panel').hidden = true;
    showNotice('Submitting selected email to your CareerShield backend…');

    try {
      const request = CareerShieldEmailUtils.buildAnalysisRequest(pendingEmail);
      const result = await requestApi('/api/analyze', {
        method: 'POST',
        body: request,
        token: auth.accessToken,
        csrfToken: auth.csrfToken,
        timeoutMs: 60000,
      });
      if (!Number.isFinite(result.trust_score) || !result.risk_level || !result.id) {
        throw new Error('CareerShield returned an incomplete analysis report.');
      }
      renderResult(result);
      showNotice(
        'Private analysis saved. Open the full report in CareerShield to review extracted details and approve any external checks.',
      );
    } catch (error) {
      if (error.status === 401) {
        auth = null;
        await chrome.storage.session.remove(['accessToken', 'csrfToken', 'account']);
        renderAuth();
        showNotice('Your session expired. Connect again from the CareerShield website.', true);
      } else {
        showNotice(error.message || 'Email analysis failed. Try again or open CareerShield.', true);
      }
    } finally {
      button.disabled = false;
      button.textContent = 'Analyze with CareerShield';
    }
  }

  function openWebsitePage(query) {
    const url = new URL(settings.webUrl);
    url.search = query;
    chrome.tabs.create({ url: url.href });
  }

  async function copySummary() {
    if (!latestResult) return;
    const summary = [
      `CareerShield preliminary recruitment assessment`,
      `Job trust score: ${latestResult.trust_score}/100`,
      `Risk level: ${latestResult.risk_level}`,
      `Confidence: ${Math.round(Number(latestResult.confidence) * 100)}%`,
      `Warnings: ${(latestResult.negative_evidence || []).join('; ') || 'None reported'}`,
      `Unknown: ${(latestResult.unknown_evidence || []).join('; ') || 'None reported'}`,
      'Decision support only; not a definitive fraud determination.',
    ].join('\n');
    try {
      await navigator.clipboard.writeText(summary);
      showNotice('Report summary copied.');
    } catch {
      showNotice('Clipboard access is unavailable in this browser context.', true);
    }
  }

  async function checkAnotherEmail() {
    pendingEmail = null;
    latestResult = null;
    await chrome.storage.session.remove(['pendingEmail', 'pendingEmailSavedAt']);
    $('result-panel').hidden = true;
    $('email-panel').hidden = true;
    showNotice('Select another email from Gmail when ready.');
  }

  async function initialize() {
    await loadSettings();
    await checkBackend();
    try {
      await loadAuth();
    } catch (error) {
      showNotice(error.message || 'Could not verify the extension session.', true);
    }
    renderAuth();

    const stored = await chrome.storage.session.get(['pendingEmail', 'pendingEmailSavedAt']);
    const age = Date.now() - (stored.pendingEmailSavedAt || 0);
    if (stored.pendingEmail && age >= 0 && age < 10 * 60 * 1000) {
      renderEmail(stored.pendingEmail);
    } else if (stored.pendingEmail) {
      await chrome.storage.session.remove(['pendingEmail', 'pendingEmailSavedAt']);
    }
  }

  $('save-settings').addEventListener('click', saveConnectionSettings);
  $('pair-button').addEventListener('click', pairAccount);
  $('sign-out').addEventListener('click', signOut);
  $('extract-email').addEventListener('click', extractCurrentEmail);
  $('analyze-email').addEventListener('click', analyzeEmail);
  $('copy-summary').addEventListener('click', copySummary);
  $('check-another').addEventListener('click', checkAnotherEmail);
  $('open-report').addEventListener('click', () => {
    if (latestResult?.id) openWebsitePage(`?analysisId=${encodeURIComponent(latestResult.id)}`);
  });
  $('open-upload').addEventListener('click', () => openWebsitePage('?page=analyze'));

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'session') return;
    if (changes.pendingEmail?.newValue) {
      renderEmail(changes.pendingEmail.newValue);
      $('result-panel').hidden = true;
      showNotice('Selected email is ready for review.');
    } else if (changes.pendingEmail) {
      renderEmail(null);
    }
  });

  initialize();
})();
