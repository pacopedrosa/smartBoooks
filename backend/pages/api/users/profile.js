import { query } from '../../../lib/db';
import { withAuth } from '../../../middleware/auth';

async function handler(req, res) {
  const userId = req.user.id;

  // --- GET /api/users/profile ---
  if (req.method === 'GET') {
    try {
      const [userResult, likesResult, favsResult, statsResult] = await Promise.all([
        query('SELECT id, name, email, created_at FROM users WHERE id = $1', [userId]),
        query(
          `SELECT b.id, b.title, b.author, b.genre, b.cover_url, l.created_at
           FROM likes l
           JOIN books b ON b.id = l.book_id
           WHERE l.user_id = $1
           ORDER BY l.created_at DESC`,
          [userId]
        ),
        query(
          `SELECT b.id, b.title, b.author, b.genre, b.cover_url, f.created_at
           FROM favorites f
           JOIN books b ON b.id = f.book_id
           WHERE f.user_id = $1
           ORDER BY f.created_at DESC`,
          [userId]
        ),
        query(
          `SELECT
             COUNT(DISTINCT l.book_id)  AS total_likes,
             COUNT(DISTINCT f.book_id)  AS total_favorites,
             COUNT(DISTINCT r.book_id)  AS total_rated
           FROM users u
           LEFT JOIN likes     l ON l.user_id = u.id
           LEFT JOIN favorites f ON f.user_id = u.id
           LEFT JOIN ratings   r ON r.user_id = u.id
           WHERE u.id = $1`,
          [userId]
        ),
      ]);

      if (userResult.rows.length === 0) {
        return res.status(404).json({ error: 'Usuario no encontrado' });
      }

      return res.status(200).json({
        user: userResult.rows[0],
        liked_books: likesResult.rows,
        favorite_books: favsResult.rows,
        stats: statsResult.rows[0],
      });
    } catch (err) {
      console.error('Profile GET error:', err);
      return res.status(500).json({ error: 'Error al obtener el perfil' });
    }
  }

  // --- PUT /api/users/profile ---
  if (req.method === 'PUT') {
    const { name } = req.body ?? {};

    if (!name || name.trim().length === 0) {
      return res.status(400).json({ error: 'El nombre es obligatorio' });
    }

    try {
      const result = await query(
        'UPDATE users SET name = $1 WHERE id = $2 RETURNING id, name, email',
        [name.trim(), userId]
      );
      return res.status(200).json({ user: result.rows[0] });
    } catch (err) {
      console.error('Profile PUT error:', err);
      return res.status(500).json({ error: 'Error al actualizar el perfil' });
    }
  }

  return res.status(405).json({ error: 'Método no permitido' });
}

export default withAuth(handler);
