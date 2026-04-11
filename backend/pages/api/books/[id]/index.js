import { query } from '../../../../lib/db';
import { withAuth } from '../../../../middleware/auth';

async function handler(req, res) {
  const bookId = parseInt(req.query.id, 10);
  if (isNaN(bookId)) {
    return res.status(400).json({ error: 'ID de libro inválido' });
  }

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  try {
    const result = await query(
      `SELECT
         b.*,
         CASE WHEN l.id IS NOT NULL THEN true ELSE false END AS is_liked,
         CASE WHEN f.id IS NOT NULL THEN true ELSE false END AS is_favorited,
         COALESCE(r.rating, 0) AS user_rating
       FROM books b
       LEFT JOIN likes     l ON l.book_id = b.id AND l.user_id = $1
       LEFT JOIN favorites f ON f.book_id = b.id AND f.user_id = $1
       LEFT JOIN ratings   r ON r.book_id = b.id AND r.user_id = $1
       WHERE b.id = $2`,
      [req.user.id, bookId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Libro no encontrado' });
    }

    return res.status(200).json({ book: result.rows[0] });
  } catch (err) {
    console.error('Book detail error:', err);
    return res.status(500).json({ error: 'Error al obtener el libro' });
  }
}

export default withAuth(handler);
