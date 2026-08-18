/**
 * QuizGen AI - API Client & Core Utilities
 */

const API_BASE_URL = (window.location.protocol === 'file:') 
  ? 'http://localhost:5000' 
  : window.location.origin;

/**
 * Perform authenticated REST API fetch requests.
 */
async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const token = localStorage.getItem('quizgen_token');

  const headers = options.headers || {};
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // If not FormData, default to application/json
  if (!(options.body instanceof FormData) && !headers['Content-Type'] && options.method && options.method !== 'GET') {
    headers['Content-Type'] = 'application/json';
  }

  options.headers = headers;

  try {
    const response = await fetch(url, options);
    const contentType = response.headers.get('content-type');
    let data;

    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = { text: await response.text() };
    }

    if (!response.ok) {
      if (response.status === 401) {
        // Token invalid or expired
        if (!window.location.pathname.includes('login.html') && !window.location.pathname.includes('register.html') && !window.location.pathname.endsWith('index.html') && window.location.pathname !== '/') {
          localStorage.removeItem('quizgen_token');
          localStorage.removeItem('quizgen_user');
          window.location.href = 'login.html?session_expired=1';
        }
      }
      const errorMsg = data.error || data.message || `Request failed with status ${response.status}`;
      throw new Error(errorMsg);
    }

    return data;
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error);
    throw error;
  }
}

/**
 * Toast Notification Utility
 */
function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const iconMap = {
    success: '✓',
    error: '✕',
    info: 'ℹ'
  };

  toast.innerHTML = `
    <span style="font-size: 1.1rem; font-weight: bold;">${iconMap[type] || 'ℹ'}</span>
    <span style="flex: 1;">${message}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(20px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}
