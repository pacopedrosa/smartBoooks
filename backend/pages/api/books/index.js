import { query } from '../../../lib/db';
import { withAuth } from '../../../middleware/auth';

async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Método no permitido' });
  }

  const { genre, search, page = '1', limit = '12' } = req.query;
  const userId = req.user.id;

  const pageNum = Math.max(1, parseInt(page, 10));
  const limitNum = Math.min(50, Math.max(1, parseInt(limit, 10)));
  const offset = (pageNum - 1) * limitNum;

  const params = [userId];
  let paramIdx = 1;
  const conditions = [];

  if (genre) {
    paramIdx++;
    conditions.push(`b.genre = $${paramIdx}`);
    params.push(genre);
  }

  if (search) {
    paramIdx++;
    conditions.push(`(b.title ILIKE $${paramIdx} OR b.author ILIKE $${paramIdx})`);
    params.push(`%${search}%`);
  }

  const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

  paramIdx++;
  const limitPlaceholder = paramIdx;
  params.push(limitNum);

  paramIdx++;
  const offsetPlaceholder = paramIdx;
  params.push(offset);

  const booksQuery = `
    SELECT
      b.*,
      CASE WHEN l.id IS NOT NULL THEN true ELSE false END AS is_liked,
      CASE WHEN f.id IS NOT NULL THEN true ELSE false END AS is_favorited,
      COALESCE(r.rating, 0) AS user_rating
    FROM books b
    LEFT JOIN likes     l ON l.book_id = b.id AND l.user_id = $1
    LEFT JOIN favorites f ON f.book_id = b.id AND f.user_id = $1
    LEFT JOIN ratings   r ON r.book_id = b.id AND r.user_id = $1
    ${whereClause}
    ORDER BY b.id ASC
    LIMIT $${limitPlaceholder} OFFSET $${offsetPlaceholder}
  `;

  // Count query (sin userId, sin LIMIT/OFFSET)
  const countParams = [];
  const countConditions = [];
  let countIdx = 0;

  if (genre) {
    countIdx++;
    countConditions.push(`genre = $${countIdx}`);
    countParams.push(genre);
  }

  if (search) {
    countIdx++;
    countConditions.push(`(title ILIKE $${countIdx} OR author ILIKE $${countIdx})`);
    countParams.push(`%${search}%`);
  }

  const countWhere =
    countConditions.length > 0 ? `WHERE ${countConditions.join(' AND ')}` : '';
  const countQuery = `SELECT COUNT(*) FROM books ${countWhere}`;

  try {
    const [booksResult, countResult] = await Promise.all([
      query(booksQuery, params),
      query(countQuery, countParams),
    ]);

    return res.status(200).json({
      books: booksResult.rows,
      total: parseInt(countResult.rows[0].count, 10),
      page: pageNum,
      limit: limitNum,
      pages: Math.ceil(parseInt(countResult.rows[0].count, 10) / limitNum),
    });
  } catch (err) {
    console.error('Books list error:', err);
    return res.status(500).json({ error: 'Error al obtener libros' });
  }
}

export default withAuth(handler);
