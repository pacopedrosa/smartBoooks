import { withAuth } from '../../middleware/auth';
import { uploadJson } from '../../lib/minio';

async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  const userId = req.user.id;
  const limit = Math.min(50, Math.max(1, parseInt(req.query.limit ?? '10', 10)));
  const mlUrl = process.env.ML_SERVICE_URL || 'http://ml-service:8000';

  try {
    const response = await fetch(`${mlUrl}/recommendations/${userId}?limit=${limit}`, {
      signal: AbortSignal.timeout(300_000), // 5 min — la primera llamada calcula embeddings de ~32k libros
    });

    if (!response.ok) {
      console.error('ML service responded with status', response.status);
      return res.status(502).json({ error: 'El servicio de recomendaciones no está disponible' });
    }

    const data = await response.json();

    // Guardar métricas en MinIO de forma asíncrona (no bloquea la respuesta)
    saveMetrics(userId, data).catch((err) =>
      console.error('Error guardando métricas en MinIO:', err)
    );

    return res.status(200).json(data);
  } catch (err) {
    console.error('Recommendations error:', err);
    return res.status(502).json({ error: 'Error al conectar con el servicio de recomendaciones' });
  }
}

/**
 * Calcula métricas del modelo y las sube a MinIO.
 *
 * Bucket : yield-predict
 * Ruta   : {userId}/metrics/metrics_{YYYY-MM-DD}.json
 *
 * @param {number} userId
 * @param {{ recommendations: Array, algorithm: string, total: number }} data
 */
async function saveMetrics(userId, data) {
  const recs   = data.recommendations ?? [];
  const scores = recs.map((r) => r.score);

  const metrics = {
    timestamp:             new Date().toISOString(),
    user_id:               userId,
    algorithm:             data.algorithm,
    total_recommendations: data.total,
    avg_score:
      scores.length > 0
        ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 10_000) / 10_000
        : 0,
    min_score:          scores.length > 0 ? Math.min(...scores) : 0,
    max_score:          scores.length > 0 ? Math.max(...scores) : 0,
    score_distribution: _buildScoreDistribution(scores),
    genres_covered:     [...new Set(recs.map((r) => r.genre).filter(Boolean))],
  };

  const dateStr    = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const objectName = `${userId}/metrics/metrics_${dateStr}.json`;

  await uploadJson(objectName, metrics);
}

/**
 * Agrupa las puntuaciones en 5 buckets de 0.2 de ancho.
 * @param {number[]} scores
 * @returns {Record<string, number>}
 */
function _buildScoreDistribution(scores) {
  const buckets = { '0.0-0.2': 0, '0.2-0.4': 0, '0.4-0.6': 0, '0.6-0.8': 0, '0.8-1.0': 0 };
  for (const s of scores) {
    if      (s < 0.2) buckets['0.0-0.2']++;
    else if (s < 0.4) buckets['0.2-0.4']++;
    else if (s < 0.6) buckets['0.4-0.6']++;
    else if (s < 0.8) buckets['0.6-0.8']++;
    else              buckets['0.8-1.0']++;
  }
  return buckets;
}

export default withAuth(handler);
