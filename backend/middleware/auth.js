import { verifyToken } from '../lib/jwt';

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3000';
const IS_PROD      = process.env.NODE_ENV === 'production';

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
    `token=${token}`,
    'HttpOnly',
    'Path=/',
    'SameSite=Strict',
    'Max-Age=604800', // 7 días en segundos
  ];
  if (IS_PROD) parts.push('Secure');
  return parts.join('; ');
}

/**
 * Genera la cabecera Set-Cookie para borrar el token (logout).
 * @returns {string}
 */
export function clearTokenCookie() {
  const parts = [
    'token=',
    'HttpOnly',
    'Path=/',
    'SameSite=Strict',
    'Max-Age=0',
  ];
  if (IS_PROD) parts.push('Secure');
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

    const token = req.cookies?.token;
    if (!token) {
      return res.status(401).json({ error: 'Sesión no iniciada' });
    }

    try {
      req.user = verifyToken(token);
      return handler(req, res);
    } catch {
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
