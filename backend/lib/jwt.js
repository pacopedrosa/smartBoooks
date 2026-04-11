import jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET;
const JWT_EXPIRES_IN = '7d';

if (!JWT_SECRET) {
  throw new Error('JWT_SECRET environment variable is not set');
}

/**
 * Genera un JWT firmado con los datos del usuario.
 * @param {{ id: number, email: string, name: string }} payload
 * @returns {string}
 */
export function signToken(payload) {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN });
}

/**
 * Verifica y decodifica un JWT.
 * @param {string} token
 * @returns {{ id: number, email: string, name: string }}
 */
export function verifyToken(token) {
  return jwt.verify(token, JWT_SECRET);
}
