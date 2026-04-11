import { clearTokenCookie } from '../../../middleware/auth';
import { withCors } from '../../../middleware/auth';

async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  res.setHeader('Set-Cookie', clearTokenCookie());
  return res.status(200).json({ message: 'Sesión cerrada correctamente' });
}

export default withCors(handler);
