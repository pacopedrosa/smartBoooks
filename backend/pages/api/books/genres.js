import { query } from '../../../lib/db';
import { withAuth } from '../../../middleware/auth';

async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  try {
    const result = await query(
      "SELECT DISTINCT genre FROM books WHERE genre IS NOT NULL ORDER BY genre"
    );
    return res.status(200).json({ genres: result.rows.map((r) => r.genre) });
  } catch (err) {
    console.error('Genres error:', err);
    return res.status(500).json({ error: 'Error al obtener géneros' });
  }
}

export default withAuth(handler);
