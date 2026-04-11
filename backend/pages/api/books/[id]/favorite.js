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
      'SELECT id FROM favorites WHERE user_id = $1 AND book_id = $2',
      [userId, bookId]
    );

    if (existing.rows.length > 0) {
      await query('DELETE FROM favorites WHERE user_id = $1 AND book_id = $2', [
        userId,
        bookId,
      ]);
      return res.status(200).json({ favorited: false, message: 'Eliminado de favoritos' });
    }

    await query('INSERT INTO favorites (user_id, book_id) VALUES ($1, $2)', [userId, bookId]);
    return res.status(201).json({ favorited: true, message: 'Añadido a favoritos' });
  } catch (err) {
    console.error('Favorite toggle error:', err);
    return res.status(500).json({ error: 'Error al procesar favorito' });
  }
}

export default withAuth(handler);
