import bcrypt from 'bcryptjs';
import { query } from '../../../lib/db';
import { signToken } from '../../../lib/jwt';
import { withCors, buildTokenCookie } from '../../../middleware/auth';

async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  const { email, password } = req.body ?? {};

  if (!email || !password) {
    return res.status(400).json({ error: 'Email y contraseña son obligatorios' });
  }

  try {
    const result = await query(
      'SELECT id, name, email, password_hash FROM users WHERE email = $1',
      [email.toLowerCase().trim()]
    );

    // Respuesta genérica para no revelar si el email existe
    if (result.rows.length === 0) {
      return res.status(401).json({ error: 'Credenciales inválidas' });
    }

    const user = result.rows[0];
    const valid = await bcrypt.compare(password, user.password_hash);

    if (!valid) {
      return res.status(401).json({ error: 'Credenciales inválidas' });
    }

    const token = signToken({ id: user.id, email: user.email, name: user.name });

    res.setHeader('Set-Cookie', buildTokenCookie(token));
    return res.status(200).json({
      user: { id: user.id, name: user.name, email: user.email },
    });
  } catch (err) {
    console.error('Login error:', err);
    return res.status(500).json({ error: 'Error interno del servidor' });
  }
}

export default withCors(handler);
