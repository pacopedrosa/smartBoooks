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

  const { rating } = req.body ?? {};
  const ratingNum = parseInt(rating, 10);

  if (!ratingNum || ratingNum < 1 || ratingNum > 5) {
    return res.status(400).json({ error: 'La valoración debe ser un número entre 1 y 5' });
  }

  const userId = req.user.id;

  try {
    // Upsert de la valoración
    await query(
      `INSERT INTO ratings (user_id, book_id, rating)
       VALUES ($1, $2, $3)
       ON CONFLICT (user_id, book_id) DO UPDATE
         SET rating = $3, updated_at = NOW()`,
      [userId, bookId, ratingNum]
    );

    // Recalcular media y total en la tabla books
    await query(
      `UPDATE books
       SET average_rating = (
             SELECT ROUND(AVG(rating)::numeric, 2) FROM ratings WHERE book_id = $1
           ),
           total_ratings = (
             SELECT COUNT(*) FROM ratings WHERE book_id = $1
           )
       WHERE id = $1`,
      [bookId]
    );

    return res.status(200).json({ message: 'Valoración guardada', rating: ratingNum });
  } catch (err) {
    console.error('Rating error:', err);
    return res.status(500).json({ error: 'Error al guardar la valoración' });
  }
}

export default withAuth(handler);
