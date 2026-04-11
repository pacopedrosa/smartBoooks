import { withAuth } from '../../../../middleware/auth';

async function handler(req, res) {
  const bookId = parseInt(req.query.id, 10);
  if (isNaN(bookId)) {
    return res.status(400).json({ error: 'ID de libro inválido' });
  }

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  const limit = Math.min(10, Math.max(1, parseInt(req.query.limit ?? '5', 10)));
  const mlUrl = process.env.ML_SERVICE_URL || 'http://ml-service:8000';

  try {
    const response = await fetch(`${mlUrl}/similar/${bookId}?limit=${limit}`, {
      signal: AbortSignal.timeout(10_000),
    });

    if (!response.ok) {
      return res.status(502).json({ error: 'El servicio de ML no está disponible' });
    }

    const data = await response.json();
    return res.status(200).json(data);
  } catch (err) {
    console.error('Similar books error:', err);
    return res.status(502).json({ error: 'Error al obtener libros similares' });
  }
}

export default withAuth(handler);
