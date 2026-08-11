const BASE_URL = import.meta.env.VITE_API_BASE_URL;
const TOKEN_KEY = 'documind_token';

let authToken = sessionStorage.getItem(TOKEN_KEY);

export function setAuthToken(token) {
  authToken = token;
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function getAuthToken() {
  return authToken;
}

export function clearAuthToken() {
  authToken = null;
  sessionStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor({ code, message, traceId, retryable, status }) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.traceId = traceId;
    this.retryable = retryable;
    this.status = status;
  }
}

async function parseErrorBody(response) {
  try {
    const body = await response.json();
    if (body && body.error) {
      return body.error;
    }
  } catch {
    return null;
  }
  return null;
}

async function request(path, { method = 'GET', body, headers = {}, isFormData = false } = {}) {
  if (!BASE_URL) {
    throw new ApiError({
      code: 'CONFIG_ERROR',
      message: 'VITE_API_BASE_URL is not set.',
      traceId: null,
      retryable: false,
      status: null,
    });
  }

  const requestHeaders = { ...headers };
  if (!isFormData) {
    requestHeaders['Content-Type'] = 'application/json';
  }
  if (authToken) {
    requestHeaders['Authorization'] = `Bearer ${authToken}`;
  }

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: requestHeaders,
      body: isFormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new ApiError({
      code: 'NETWORK_ERROR',
      message: err.message || 'Network request failed.',
      traceId: null,
      retryable: true,
      status: null,
    });
  }

  if (!response.ok) {
    const error = await parseErrorBody(response);
    throw new ApiError({
      code: error?.code || 'INTERNAL',
      message: error?.message || response.statusText || 'Request failed.',
      traceId: error?.trace_id ?? null,
      retryable: error?.retryable ?? false,
      status: response.status,
    });
  }

  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.blob();
}

export function login(email, password) {
  return request('/auth/login', { method: 'POST', body: { email, password } });
}

export function uploadDocument(file, dataClassification) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('data_classification', dataClassification);
  return request('/documents', { method: 'POST', body: formData, isFormData: true });
}

export function getDocumentStatus(documentId) {
  return request(`/documents/${documentId}/status`);
}

export function getExtraction(documentId) {
  return request(`/documents/${documentId}/extraction`);
}

export function getDocumentFile(documentId) {
  return request(`/documents/${documentId}/file`);
}

export function correctExtraction(documentId, corrections) {
  return request(`/documents/${documentId}/extraction`, {
    method: 'PATCH',
    body: { corrections },
  });
}

export function createExport(documentIds, format) {
  return request('/exports', {
    method: 'POST',
    body: { document_ids: documentIds, format },
  });
}

export function getExportStatus(exportId) {
  return request(`/exports/${exportId}`);
}

export function downloadExport(exportId) {
  return request(`/exports/${exportId}/file`);
}

export function listDocuments(params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, value);
    }
  }
  const qs = query.toString();
  return request(`/documents${qs ? `?${qs}` : ''}`);
}
