import { withAuth } from '../../middleware/auth';

async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  const userId = req.user.id;
  const limit = Math.min(50, Math.max(1, parseInt(req.query.limit ?? '10', 10)));
  const mlUrl = process.env.ML_SERVICE_URL || 'http://ml-service:8000';

  try {
    const response = await fetch(`${mlUrl}/recommendations/${userId}?limit=${limit}`, {
      signal: AbortSignal.timeout(10_000),
    });

    if (!response.ok) {
      console.error('ML service responded with status', response.status);
      return res.status(502).json({ error: 'El servicio de recomendaciones no está disponible' });
    }

    const data = await response.json();
    return res.status(200).json(data);
  } catch (err) {
    console.error('Recommendations error:', err);
    return res.status(502).json({ error: 'Error al conectar con el servicio de recomendaciones' });
  }
}

export default withAuth(handler);
