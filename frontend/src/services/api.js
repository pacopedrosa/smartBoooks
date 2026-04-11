import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
  // Necesario para que el navegador envíe/reciba la cookie httpOnly
  withCredentials: true,
});

// Si el servidor responde 401, limpiamos el usuario en localStorage y redirigimos
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('sb_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login:    (data) => api.post('/auth/login', data),
  logout:   ()     => api.post('/auth/logout'),
};

// ── Books ─────────────────────────────────────────────────
export const booksAPI = {
  list:    (params) => api.get('/books', { params }),
  detail:  (id)     => api.get(`/books/${id}`),
  genres:  ()       => api.get('/books/genres'),
  like:    (id)     => api.post(`/books/${id}/like`),
  fav:     (id)     => api.post(`/books/${id}/favorite`),
  rate:    (id, rating) => api.post(`/books/${id}/rate`, { rating }),
  similar: (id)     => api.get(`/books/${id}/similar`),
};

// ── Recommendations ───────────────────────────────────────
export const recsAPI = {
  get: (limit = 10) => api.get('/recommendations', { params: { limit } }),
};

// ── User ──────────────────────────────────────────────────
export const userAPI = {
  profile:       ()     => api.get('/users/profile'),
  updateProfile: (data) => api.put('/users/profile', data),
};

export default api;
