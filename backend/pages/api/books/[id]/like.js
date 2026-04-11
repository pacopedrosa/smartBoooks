import { query } from '../../../../lib/db';
import { withAuth } from '../../../../middleware/auth';

async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  const bookId = parseInt(req.query.id, 10);
  if (isNaN(bookId)) {
    return res.status(400).json({ error: 'ID de libro inválido' });
  }

  const userId = req.user.id;

  try {
    const existing = await query(
      'SELECT id FROM likes WHERE user_id = $1 AND book_id = $2',
      [userId, bookId]
    );

    if (existing.rows.length > 0) {
      await query('DELETE FROM likes WHERE user_id = $1 AND book_id = $2', [userId, bookId]);
      return res.status(200).json({ liked: false, message: 'Like eliminado' });
    }

    await query('INSERT INTO likes (user_id, book_id) VALUES ($1, $2)', [userId, bookId]);
    return res.status(201).json({ liked: true, message: 'Like añadido' });
  } catch (err) {
    console.error('Like toggle error:', err);
    return res.status(500).json({ error: 'Error al procesar el like' });
  }
}

export default withAuth(handler);
