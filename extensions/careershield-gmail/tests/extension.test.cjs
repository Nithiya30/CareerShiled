const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const extensionRoot = path.resolve(__dirname, '..');
const read = (file) => fs.readFileSync(path.join(extensionRoot, file), 'utf8');

function emailUtils() {
  const context = { URL };
  context.globalThis = context;
  vm.runInNewContext(read('email-utils.js'), context);
  return context.CareerShieldEmailUtils;
}

test('manifest is MV3 and requests only Gmail plus extension storage and tabs', () => {
  const manifest = JSON.parse(read('manifest.json'));
  assert.equal(manifest.manifest_version, 3);
  assert.deepEqual(manifest.content_scripts[0].matches, ['https://mail.google.com/*']);
  assert.ok(manifest.permissions.includes('storage'));
  assert.ok(manifest.permissions.includes('activeTab'));
  assert.ok(!manifest.permissions.includes('tabs'));
  assert.ok(!manifest.permissions.includes('identity'));
  assert.ok(!manifest.host_permissions.some((origin) => origin.includes('gmail.googleapis.com')));
});

test('content script only activates on Gmail', () => {
  const utils = emailUtils();
  assert.equal(utils.isGmailUrl('https://mail.google.com/mail/u/0/#inbox'), true);
  assert.equal(utils.isGmailUrl('http://mail.google.com/'), false);
  assert.equal(utils.isGmailUrl('https://example.com/'), false);
  assert.equal(utils.isGmailUrl('https://mail.google.com.attacker.test/'), false);
});

test('email subject, sender, links, and visible attachment names map to analysis input', () => {
  const request = emailUtils().buildAnalysisRequest({
    subject: 'Senior Engineer role',
    sender_name: 'Recruiter',
    sender_email: 'Recruiter@Example.test',
    body: 'Please apply for the software position.',
    date: 'Oct 30',
    links: [
      { url: 'https://jobs.example.test/opening', label: 'Apply' },
      { url: 'javascript:alert(1)', label: 'bad link' },
    ],
    attachments: [{ filename: 'role.pdf', mime_type: 'application/pdf' }],
  });
  assert.equal(request.job_title, 'Senior Engineer role');
  assert.equal(request.analysis_mode, 'private_email');
  assert.equal(request.recruiter_email, 'recruiter@example.test');
  assert.match(request.job_description, /Email subject: Senior Engineer role/);
  assert.match(request.job_description, /https:\/\/jobs\.example\.test\/opening/);
  assert.doesNotMatch(request.job_description, /javascript:/);
  assert.match(request.job_description, /role\.pdf \(application\/pdf\)/);
  assert.equal(request.document_source, true);
  assert.equal(request.company_name, '');
});

test('email verification fields are extracted locally and tracking query data is removed', () => {
  const request = emailUtils().buildAnalysisRequest({
    subject: 'Recruitment email',
    sender_name: 'Jane Recruiter',
    sender_email: 'recruiter@acme.example',
    body: [
      'Company: Acme Systems',
      'Job Title: Platform Engineer',
      'Location: Remote',
      'Salary: $100,000 - $120,000',
      'Official website: https://acme.example/jobs?tracking=private',
      'Please review the role.',
    ].join('\n'),
  });

  assert.equal(request.company_name, 'Acme Systems');
  assert.equal(request.job_title, 'Platform Engineer');
  assert.equal(request.company_website, 'https://acme.example/jobs');
  assert.equal(request.location, 'Remote');
  assert.equal(request.salary, '$100,000 - $120,000');
  assert.equal(request.recruiter_email, 'recruiter@acme.example');
  assert.doesNotMatch(request.company_website, /tracking=private/);
});

test('email body is required and untrusted link schemes are excluded', () => {
  const utils = emailUtils();
  assert.equal(utils.buildAnalysisRequest({
    subject: '',
    sender_email: 'recruiter@example.test',
    body: 'A role is available.',
  }).job_title, 'Recruitment email');
  assert.throws(() => utils.buildAnalysisRequest({
    sender_email: 'recruiter@example.test',
    body: '   ',
  }), /no readable message body/);
  assert.throws(() => utils.buildAnalysisRequest({
    sender_email: 'not-an-email',
    body: 'An email body',
  }), /sender address/);
  assert.deepEqual(
    utils.normalizeLinks([{ url: 'javascript:alert(1)' }, { url: 'file:///secret' }]),
    [],
  );
});

test('Gmail content extraction is user-triggered and does not read attachment contents', () => {
  const content = read('content.js');
  assert.match(content, /button\.addEventListener\('click', async \(\) => \{/);
  assert.match(content, /saveSelectedEmail\(\)/);
  assert.match(content, /new MutationObserver\(scheduleButtonUpdate\)/);
  assert.match(content, /const existing = document\.querySelectorAll/);
  assert.match(content, /target\.querySelector\(`#\$\{BUTTON_ID\}`\)/);
  assert.doesNotMatch(content, /fetch\s*\(/);
  assert.doesNotMatch(content, /XMLHttpRequest/);
  assert.match(content, /readAttachments/);
  assert.doesNotMatch(content, /download_url|\.download\s*\(/);
});

test('popup defines loading, result, error, and authentication recovery controls', () => {
  const html = read('popup.html');
  const script = read('popup.js');
  assert.match(html, /Analyze with CareerShield/);
  assert.match(html, /JOB TRUST SCORE/);
  assert.match(html, /Unknown \/ unavailable/);
  assert.match(html, /Sender domain observations/);
  assert.match(html, /Sign out/);
  assert.match(html, /View report &amp; review optional checks/);
  assert.match(script, /Your extension session expired/);
  assert.match(script, /Analyzing recruitment signals/);
  assert.match(script, /approve any external checks/);
  assert.match(script, /requestApi\('\/api\/analyze'/);
  assert.match(script, /body: request/);
  assert.match(script, /risk\.includes\('uncertain'\)/);
});
