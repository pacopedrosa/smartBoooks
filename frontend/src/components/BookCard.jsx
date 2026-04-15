import { useState } from 'react';
import { booksAPI } from '../services/api';

function StarInput({ value, onChange }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          className="text-xl transition-transform hover:scale-125 bg-transparent border-0 cursor-pointer"
          onMouseEnter={() => setHover(n)}
          onMouseLeave={() => setHover(0)}
          onClick={() => onChange(n)}
          title={`Valorar con ${n}`}
        >
          {n <= (hover || value) ? '⭐' : '☆'}
        </button>
      ))}
    </div>
  );
}

function renderStars(rating) {
  const r = Math.round(Number(rating));
  return '⭐'.repeat(Math.min(5, Math.max(0, r))) + '☆'.repeat(5 - Math.min(5, Math.max(0, r)));
}

export default function BookCard({ book, onUpdate }) {
  const [liked,      setLiked]      = useState(book.is_liked);
  const [favorited,  setFavorited]  = useState(book.is_favorited);
  const [userRating, setUserRating] = useState(book.user_rating || 0);
  const [loading,    setLoading]    = useState(false);

  async function toggleLike() {
    if (loading) return;
    setLoading(true);
    try {
      const { data } = await booksAPI.like(book.id);
      setLiked(data.liked);
      onUpdate?.({ ...book, is_liked: data.liked });
    } catch { /* silencioso */ } finally { setLoading(false); }
  }

  async function toggleFav() {
    if (loading) return;
    setLoading(true);
    try {
      const { data } = await booksAPI.fav(book.id);
      setFavorited(data.favorited);
      onUpdate?.({ ...book, is_favorited: data.favorited });
    } catch { /* silencioso */ } finally { setLoading(false); }
  }

  async function handleRate(rating) {
    setLoading(true);
    try {
      await booksAPI.rate(book.id, rating);
      setUserRating(rating);
    } catch { /* silencioso */ } finally { setLoading(false); }
  }

  return (
    <div className="bg-white rounded-xl shadow-md hover:shadow-xl hover:-translate-y-1 transition-all duration-200 overflow-hidden flex flex-col">
      {/* Portada */}
      <div className="relative aspect-[2/3] bg-gradient-to-br from-slate-100 to-slate-200 overflow-hidden">
        {book.cover_url ? (
          <img src={book.cover_url} alt={book.title} loading="lazy" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-slate-400 p-4 text-center">
            <span className="text-5xl">📖</span>
            <span className="text-xs font-semibold leading-tight">{book.title}</span>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3 flex flex-col gap-1.5 flex-1">
        <h3 className="text-sm font-bold leading-tight line-clamp-2">{book.title}</h3>
        <p className="text-xs text-slate-500">{book.author}</p>

        <div className="flex flex-wrap gap-1.5 items-center">
          {book.genre && (
            <span className="bg-blue-50 text-[#1e3a5f] text-[11px] font-semibold px-2 py-0.5 rounded">
              {book.genre}
            </span>
          )}
          {book.format && (
            <span className="bg-slate-100 text-slate-500 text-[11px] px-2 py-0.5 rounded">
              {book.format}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 text-xs text-slate-500">
          <span className="text-amber-400">{renderStars(book.average_rating)}</span>
          <span>{Number(book.average_rating).toFixed(1)} ({book.total_ratings})</span>
        </div>

        {book.price != null && (
          <div className="flex items-baseline gap-1.5">
            <span className="text-sm font-bold text-[#1e3a5f]">
              {book.currency ?? '$'}{Number(book.price).toFixed(2)}
            </span>
            {book.old_price && Number(book.old_price) > Number(book.price) && (
              <span className="text-[11px] text-slate-400 line-through">
                {book.currency ?? '$'}{Number(book.old_price).toFixed(2)}
              </span>
            )}
          </div>
        )}

        <StarInput value={userRating} onChange={handleRate} />
      </div>

      {/* Acciones */}
      <div className="px-3 pb-3 pt-2 border-t border-slate-100 flex items-center justify-between">
        <div className="flex gap-2">
          <button
            onClick={toggleLike}
            disabled={loading}
            title={liked ? 'Quitar like' : 'Me gusta'}
            className={`text-2xl transition-transform hover:scale-125 disabled:opacity-50 bg-transparent border-0 cursor-pointer ${liked ? 'text-red-500' : 'text-slate-300'}`}
          >
            {liked ? '❤️' : '🤍'}
          </button>
          <button
            onClick={toggleFav}
            disabled={loading}
            title={favorited ? 'Quitar de favoritos' : 'Añadir a favoritos'}
            className={`text-2xl transition-transform hover:scale-125 disabled:opacity-50 bg-transparent border-0 cursor-pointer ${favorited ? 'text-amber-400' : 'text-slate-300'}`}
          >
            {favorited ? '🔖' : '📄'}
          </button>
        </div>
        {book.pages && (
          <span className="text-[11px] text-slate-400">{book.pages} pág.</span>
        )}
      </div>
    </div>
  );
}
