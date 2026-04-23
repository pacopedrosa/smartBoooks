import { verifyToken } from '../lib/jwt';

const FRONTEND_URL  = process.env.FRONTEND_URL  || 'http://localhost:3000';
const COOKIE_SECURE = process.env.COOKIE_SECURE === 'true';

function setCorsHeaders(res) {
  res.setHeader('Access-Control-Allow-Origin',  FRONTEND_URL);
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
}

/**
 * Genera la cabecera Set-Cookie para el token JWT como cookie httpOnly.
 * @param {string} token
 * @returns {string}
 */
export function buildTokenCookie(token) {
  const parts = [
    `sb_token=${token}`,
    'HttpOnly',
    'Path=/',
    'SameSite=Lax',
    'Max-Age=604800', // 7 días en segundos
  ];
  if (COOKIE_SECURE) parts.push('Secure');
  return parts.join('; ');
}

/**
 * Genera la cabecera Set-Cookie para borrar el token (logout).
 * @returns {string}
 */
export function clearTokenCookie() {
  const parts = [
    'sb_token=',
    'HttpOnly',
    'Path=/',
    'SameSite=Lax',
    'Max-Age=0',
  ];
  if (COOKIE_SECURE) parts.push('Secure');
  return parts.join('; ');
}

/**
 * Middleware que añade CORS y valida el JWT de la cookie httpOnly.
 * El objeto `req.user` quedará disponible en el handler con { id, email, name }.
 */
export function withAuth(handler) {
  return async (req, res) => {
    setCorsHeaders(res);

    if (req.method === 'OPTIONS') {
      return res.status(200).end();
    }

    console.log(`[AUTH MW] ${req.method} ${req.url} | cookies:`, Object.keys(req.cookies ?? {}));

    const token = req.cookies?.sb_token;
    if (!token) {
      console.warn(`[AUTH MW] 401 — sin cookie sb_token en ${req.url}`);
      return res.status(401).json({ error: 'Sesión no iniciada' });
    }

    try {
      req.user = verifyToken(token);
      console.log(`[AUTH MW] Token válido para user ${req.user.id} en ${req.url}`);
      return handler(req, res);
    } catch (e) {
      console.warn(`[AUTH MW] 401 — token inválido en ${req.url}:`, e.message);
      return res.status(401).json({ error: 'Sesión inválida o expirada' });
    }
  };
}

/**
 * Middleware que sólo añade cabeceras CORS (sin autenticación).
 * Úsalo en las rutas públicas como /auth/register y /auth/login.
 */
export function withCors(handler) {
  return async (req, res) => {
    setCorsHeaders(res);

    if (req.method === 'OPTIONS') {
      return res.status(200).end();
    }

    return handler(req, res);
  };
}
