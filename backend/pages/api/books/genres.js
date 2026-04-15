import { query } from '../../../lib/db';
import { withAuth } from '../../../middleware/auth';

async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  try {
    const [genresResult, formatsResult] = await Promise.all([
      query("SELECT DISTINCT genre FROM books WHERE genre IS NOT NULL ORDER BY genre"),
      query("SELECT DISTINCT format FROM books WHERE format IS NOT NULL ORDER BY format"),
    ]);

    return res.status(200).json({
      genres:  genresResult.rows.map((r) => r.genre),
      formats: formatsResult.rows.map((r) => r.format),
    });
  } catch (err) {
    console.error('Genres error:', err);
    return res.status(500).json({ error: 'Error al obtener géneros' });
  }
}

export default withAuth(handler);
