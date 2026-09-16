export class ApiError extends Error {
  constructor(public status: number, public message: string, public data?: any) {
    super(message);
    this.name = 'ApiError';
  }
}

const explicitBaseUrl = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, '');

// In development the Vite dev server proxies /api/v1 to FastAPI, so the app can
// stay same-origin (no CORS, works behind tunnels and sandbox preview hosts).
const API_BASE_URL =
  explicitBaseUrl || (import.meta.env.DEV ? '/api/v1' : 'http://127.0.0.1:8000/api/v1');

export const getAuthToken = () => {
  return localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
};

export const setAuthToken = (token: string, rememberMe: boolean = true) => {
  if (rememberMe) {
    localStorage.setItem('access_token', token);
    sessionStorage.removeItem('access_token');
  } else {
    sessionStorage.setItem('access_token', token);
    localStorage.removeItem('access_token');
  }
};

export const removeAuthToken = () => {
  localStorage.removeItem('access_token');
  sessionStorage.removeItem('access_token');
};

interface RequestOptions extends RequestInit {
  data?: any;
}

export const client = async <T>(endpoint: string, options: RequestOptions = {}): Promise<T> => {
  const { data, headers: customHeaders, ...customConfig } = options;
  const token = getAuthToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(customHeaders as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config: RequestInit = {
    method: data ? 'POST' : 'GET',
    ...customConfig,
    headers,
  };

  if (data) {
    config.body = JSON.stringify(data);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, config);
  } catch (error) {
    // Network errors (e.g. server down, CORS)
    throw new ApiError(0, 'Network Error. Please check your connection.');
  }

  if (response.ok) {
    // Check if the response is empty
    if (response.status === 204) {
      return {} as T;
    }
    const result = await response.json();
    return result as T;
  } else {
    // Handle specific status codes
    if (response.status === 401) {
      removeAuthToken();
      // We could trigger a global event here or let the AuthContext handle it based on token absence
      window.dispatchEvent(new CustomEvent('unauthorized'));
    }

    const errorData = await response.json().catch(() => null);
    const errorMessage = errorData?.detail || errorData?.message || `API Error: ${response.statusText}`;
    throw new ApiError(response.status, errorMessage, errorData);
  }
};
