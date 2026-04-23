import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '';

console.log('[API] VITE_API_URL =', import.meta.env.VITE_API_URL);
console.log('[API] baseURL =', `${API_BASE}/api`);

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 310_000, // 5 min + margen — las recomendaciones pueden tardar en el primer arranque
  // Necesario para que el navegador envíe/reciba la cookie httpOnly
  withCredentials: true,
});

// Log de todas las peticiones
api.interceptors.request.use((config) => {
  console.log(`[API REQUEST] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`, {
    data: config.data,
    withCredentials: config.withCredentials,
  });
  return config;
});

// Si el servidor responde 401, limpiamos el usuario en localStorage y redirigimos
api.interceptors.response.use(
  (res) => {
    console.log(`[API RESPONSE] ${res.status} ${res.config.url}`, res.data);
    return res;
  },
  (err) => {
    console.error(
      `[API ERROR] ${err.response?.status ?? 'Network'} ${err.config?.url}`,
      err.response?.data ?? err.message
    );
    if (err.response?.status === 401) {
      console.warn('[API] 401 detectado — limpiando sesión y redirigiendo a /login');
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
