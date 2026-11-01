globalThis.CareerShieldEmailUtils = (() => {
  const MAX_BODY_LENGTH = 100_000;
  const MAX_LINKS = 30;
  const MAX_ATTACHMENTS = 20;

  function normalizeText(value, maxLength = MAX_BODY_LENGTH) {
    return String(value || '')
      .replace(/\r\n?/g, '\n')
      .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '')
      .split('\n')
      .map((line) => line.replace(/[^\S\n]+/g, ' ').trim())
      .join('\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
      .slice(0, maxLength);
  }

  function safeLink(href, label = '') {
    try {
      const url = new URL(href);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null;
      return {
        url: url.href.slice(0, 2048),
        label: normalizeText(label, 200),
      };
    } catch {
      return null;
    }
  }

  function normalizeLinks(links) {
    const seen = new Set();
    return (links || [])
      .map((link) => safeLink(link.url || link.href, link.label || link.text))
      .filter((link) => {
        if (!link || seen.has(link.url)) return false;
        seen.add(link.url);
        return true;
      })
      .slice(0, MAX_LINKS);
  }

  function normalizeAttachments(attachments) {
    return (attachments || [])
      .slice(0, MAX_ATTACHMENTS)
      .map((attachment) => {
        const filename = normalizeText(attachment.filename, 255);
        const extension = filename.includes('.')
          ? filename.split('.').pop().toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 12)
          : '';
        return {
          filename,
          extension,
          mime_type: normalizeText(attachment.mime_type, 120) || 'Unknown',
        };
      })
      .filter((attachment) => attachment.filename);
  }

  function labeledValue(text, label) {
    const pattern = new RegExp(`^\\s*${label}\\s*:\\s*(.{1,200})$`, 'im');
    const match = pattern.exec(text);
    return match ? normalizeText(match[1], 200) : '';
  }

  function companyWebsite(body, links) {
    const explicit = labeledValue(
      body,
      '(?:company website|official website|company site|website)',
    );
    const labeledLink = (links || []).find((link) =>
      /(?:company|official|career|website)/i.test(link.label || link.text || ''),
    );
    const candidate = explicit || (labeledLink && (labeledLink.url || labeledLink.href)) || '';
    const safe = safeLink(candidate);
    if (!safe) return '';
    try {
      const url = new URL(safe.url);
      url.search = '';
      url.hash = '';
      return url.href;
    } catch {
      return '';
    }
  }

  function buildAnalysisRequest(email) {
    const subject = normalizeText(email.subject, 500);
    const senderName = normalizeText(email.sender_name, 200);
    const senderEmail = normalizeText(email.sender_email, 320).toLowerCase();
    const body = normalizeText(email.body);
    if (!body) throw new Error('The selected email has no readable message body.');
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(senderEmail)) {
      throw new Error('The selected email sender address could not be read.');
    }

    const links = normalizeLinks(email.links);
    const attachments = normalizeAttachments(email.attachments);
    const labeledTitle = labeledValue(body, '(?:job title|position|role)');
    const metadata = [
      `Email subject: ${subject || '(not available)'}`,
      `Sender name: ${senderName || '(not available)'}`,
      `Sender email: ${senderEmail}`,
      email.date ? `Email date: ${normalizeText(email.date, 120)}` : '',
      links.length
        ? `Links in message:\n${links.map((link) => `- ${link.url}`).join('\n')}`
        : 'Links in message: Unknown / none visible',
      attachments.length
        ? `Visible attachment names only (contents not accessed):\n${attachments
          .map((item) => `- ${item.filename} (${item.mime_type})`)
          .join('\n')}`
        : '',
    ].filter(Boolean);

    return {
      job_title: labeledTitle || subject || 'Recruitment email',
      analysis_mode: 'private_email',
      company_name: labeledValue(body, '(?:company|employer|hiring company)'),
      recruiter_email: senderEmail,
      company_website: companyWebsite(body, email.links),
      location: labeledValue(body, '(?:job )?location'),
      employment_type: 'Full-time',
      salary: labeledValue(body, '(?:salary|compensation|pay range|salary range)'),
      job_description: `${metadata.join('\n\n')}\n\nEmail body:\n${body}`.slice(
        0,
        MAX_BODY_LENGTH + 10_000,
      ),
      requirements: '',
      benefits: '',
      document_source: true,
    };
  }

  function isGmailUrl(value) {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && url.hostname === 'mail.google.com';
    } catch {
      return false;
    }
  }

  return {
    buildAnalysisRequest,
    isGmailUrl,
    normalizeAttachments,
    normalizeLinks,
    normalizeText,
    labeledValue,
    companyWebsite,
    safeLink,
  };
})();
