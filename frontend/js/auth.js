/**
 * QuizGen AI - Authentication Helpers & State Management
 */

function getToken() {
  return localStorage.getItem('quizgen_token');
}

function getCurrentUser() {
  const userStr = localStorage.getItem('quizgen_user');
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch {
    return null;
  }
}

function isLoggedIn() {
  return !!getToken();
}

function requireAuth() {
  if (!isLoggedIn()) {
    window.location.href = `login.html?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`;
  }
}

function requireGuest() {
  if (isLoggedIn()) {
    window.location.href = 'dashboard.html';
  }
}

async function handleLogin(email, password) {
  try {
    const data = await fetchAPI('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });

    localStorage.setItem('quizgen_token', data.token);
    localStorage.setItem('quizgen_user', JSON.stringify(data.user));

    showToast('Login successful! Redirecting...', 'success');
    
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get('redirect') || 'dashboard.html';
    setTimeout(() => {
      window.location.href = redirect;
    }, 800);
  } catch (error) {
    showToast(error.message || 'Login failed. Please check your credentials.', 'error');
    throw error;
  }
}

async function handleRegister(name, email, password, confirmPassword, role = 'student') {
  try {
    const data = await fetchAPI('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        name,
        email,
        password,
        confirm_password: confirmPassword,
        role
      })
    });

    localStorage.setItem('quizgen_token', data.token);
    localStorage.setItem('quizgen_user', JSON.stringify(data.user));

    showToast('Account created successfully! Redirecting...', 'success');
    setTimeout(() => {
      window.location.href = 'dashboard.html';
    }, 800);
  } catch (error) {
    showToast(error.message || 'Registration failed.', 'error');
    throw error;
  }
}

function handleLogout() {
  try {
    fetchAPI('/api/auth/logout', { method: 'POST' }).catch(() => {});
  } finally {
    localStorage.removeItem('quizgen_token');
    localStorage.removeItem('quizgen_user');
    showToast('You have been logged out.', 'info');
    setTimeout(() => {
      window.location.href = 'login.html';
    }, 500);
  }
}

function updateNavigationAuthUI() {
  const navContainer = document.querySelector('.nav-actions');
  const navMenu = document.querySelector('.nav-menu');
  if (!navContainer) return;

  const user = getCurrentUser();

  if (user) {
    // Logged in UI
    if (navMenu) {
      navMenu.innerHTML = `
        <li><a href="dashboard.html" class="nav-link ${window.location.pathname.includes('dashboard') ? 'active' : ''}">📊 Dashboard</a></li>
        <li><a href="generate.html" class="nav-link ${window.location.pathname.includes('generate') ? 'active' : ''}">✨ Create Quiz</a></li>
        <li><a href="flashcards.html" class="nav-link ${window.location.pathname.includes('flashcards') ? 'active' : ''}">🗂️ Flashcards</a></li>
      `;
    }

    navContainer.innerHTML = `
      <div style="display: flex; align-items: center; gap: 0.8rem;">
        <span style="font-size: 0.9rem; font-weight: 600; color: var(--text-secondary);">
          👤 ${escapeHTML(user.name || user.email)}
        </span>
        <button onclick="handleLogout()" class="btn btn-secondary btn-sm" title="Log out">
          Sign Out
        </button>
      </div>
    `;
  } else {
    // Guest UI
    if (navMenu) {
      navMenu.innerHTML = `
        <li><a href="index.html" class="nav-link">Home</a></li>
        <li><a href="index.html#features" class="nav-link">Features</a></li>
        <li><a href="index.html#how-it-works" class="nav-link">How It Works</a></li>
      `;
    }

    navContainer.innerHTML = `
      <a href="login.html" class="btn btn-secondary btn-sm">Login</a>
      <a href="register.html" class="btn btn-primary btn-sm">Get Started</a>
    `;
  }

  // Setup mobile toggle
  const toggleBtn = document.querySelector('.mobile-toggle');
  if (toggleBtn && navMenu) {
    toggleBtn.onclick = () => {
      navMenu.classList.toggle('active');
    };
  }
}

function escapeHTML(str) {
  if (!str) return '';
  return str.replace(/[&<>'"]/g, 
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}

document.addEventListener('DOMContentLoaded', () => {
  updateNavigationAuthUI();
});
