const API_BASE_URL = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;

function readCsrfToken() {
  const entry = document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('careershield_csrf='));
  return entry ? decodeURIComponent(entry.slice('careershield_csrf='.length)) : null;
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();
  const csrfToken = readCsrfToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken
      ? { 'X-CSRF-Token': csrfToken }
      : {}),
    ...(options.headers || {})
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include'
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const error = new Error(errorData.detail || `Request failed with status ${response.status}`);
      error.status = response.status;
      if (
        response.status === 401
        && !['/api/auth/login', '/api/auth/register', '/api/auth/me'].includes(endpoint)
      ) {
        window.dispatchEvent(new Event('careershield:unauthorized'));
      }
      throw error;
    }

    if (response.status === 204) return null;
    return await response.json();
  } catch (error) {
    console.error(`API Error on ${endpoint}:`, error);
    throw error;
  }
}

function extractDocument(file, onProgress) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('POST', `${API_BASE_URL}/api/documents/extract`);
    request.withCredentials = true;
    const csrfToken = readCsrfToken();
    if (csrfToken) request.setRequestHeader('X-CSRF-Token', csrfToken);

    request.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });
    request.addEventListener('load', () => {
      let responseData = {};
      try {
        responseData = JSON.parse(request.responseText);
      } catch {
        responseData = {};
      }

      if (request.status >= 200 && request.status < 300) {
        resolve(responseData);
        return;
      }

      if (request.status === 401) {
        window.dispatchEvent(new Event('careershield:unauthorized'));
      }
      reject(new Error(responseData.detail || `Upload failed with status ${request.status}`));
    });
    request.addEventListener('error', () => {
      reject(new Error('Upload failed. Check your connection and try again.'));
    });

    const formData = new FormData();
    formData.append('file', file);
    request.send(formData);
  });
}

export const api = {
  // Authentication
  register: (userData) => request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(userData)
  }),
  login: (credentials) => request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials)
  }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  getCurrentUser: () => request('/api/auth/me'),
  createExtensionPairing: () => request('/api/auth/extension/pairing', {
    method: 'POST'
  }),
  startGmailOAuth: () => request('/api/gmail/oauth/start', {
    method: 'POST'
  }),
  getGmailAccount: () => request('/api/gmail/account'),
  disconnectGmailAccount: () => request('/api/gmail/account', {
    method: 'DELETE'
  }),
  getGmailMonitoringStatus: () => request('/api/gmail/monitoring'),
  enableGmailMonitoring: () => request('/api/gmail/monitoring/enable', {
    method: 'POST',
    body: JSON.stringify({ consent: true })
  }),
  pauseGmailMonitoring: () => request('/api/gmail/monitoring/pause', {
    method: 'POST'
  }),
  resumeGmailMonitoring: () => request('/api/gmail/monitoring/resume', {
    method: 'POST',
    body: JSON.stringify({ consent: true })
  }),

  // System & Health
  getHealth: () => request('/api/health'),
  getModelStatus: () => request('/api/model/status'),
  getDatasetsStatus: () => request('/api/datasets/status'),
  getMetrics: () => request('/api/metrics'),

  // Recruitment Analysis
  analyzeJob: (jobData) => request('/api/analyze', {
    method: 'POST',
    body: JSON.stringify(jobData)
  }),
  extractDocument,
  getAnalysis: (id) => request(`/api/analysis/${id}`),
  saveExternalVerificationConsent: (id, consent, selectedChecks = []) => request(
    `/api/analyses/${id}/external-verification/consent`,
    {
      method: 'POST',
      body: JSON.stringify({ consent, selected_checks: selectedChecks })
    }
  ),
  getExternalVerificationStatus: (id) => request(
    `/api/analyses/${id}/external-verification`
  ),
  runExternalVerification: (id) => request(
    `/api/analyses/${id}/external-verification/run`,
    { method: 'POST' }
  ),
  getHistory: (params = {}) => {
    const query = new URLSearchParams();
    if (params.risk) query.append('risk', params.risk);
    if (params.search) query.append('search', params.search);
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return request(`/api/history${queryString}`);
  },

  // Company Intelligence
  getCompanyReputation: (companyName) => request(`/api/company/${encodeURIComponent(companyName)}/reputation`),
  analyzeCompanyReputation: (companyName) => request('/api/company/reputation', {
    method: 'POST',
    body: JSON.stringify({ company_name: companyName })
  }),
  analyzeReview: (reviewData) => request('/api/reviews/analyze', {
    method: 'POST',
    body: JSON.stringify(reviewData)
  }),
  analyzeClaim: (companyName, claimText) => request('/api/company/claims', {
    method: 'POST',
    body: JSON.stringify({ company_name: companyName, claim: claimText })
  }),
  createCompanyInvestigation: (investigation) => request('/api/company/investigations', {
    method: 'POST',
    body: JSON.stringify(investigation)
  }),
  getCompanyInvestigations: () => request('/api/company/investigations'),
  getCompanyInvestigation: (id) => request(`/api/company/investigations/${encodeURIComponent(id)}`),
  getCompanyInvestigationGraph: (id) => request(`/api/company/investigations/${encodeURIComponent(id)}/graph`),
  deleteCompanyInvestigation: (id) => request(`/api/company/investigations/${encodeURIComponent(id)}`, {
    method: 'DELETE'
  })
};

export default api;
