import { useState, useEffect, useCallback } from 'react';
import { booksAPI } from '../services/api';
import BookCard from '../components/BookCard';

function Spinner() {
  return (
    <div className="flex justify-center py-16">
      <div className="w-10 h-10 border-4 border-slate-200 border-t-[#1e3a5f] rounded-full animate-spin-custom" />
    </div>
  );
}

export default function Books() {
  const [books,   setBooks]   = useState([]);
  const [genres,  setGenres]  = useState([]);
  const [formats, setFormats] = useState([]);
  const [total,   setTotal]   = useState(0);
  const [pages,   setPages]   = useState(1);
  const [page,    setPage]    = useState(1);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  const [filters,    setFilters]    = useState({ search: '', genre: '', format: '' });
  const [draftSearch, setDraftSearch] = useState('');

  const fetchGenres = useCallback(async () => {
    try {
      const { data } = await booksAPI.genres();
      setGenres(data.genres);
      setFormats(data.formats ?? []);
    } catch { /* no crítico */ }
  }, []);

  const fetchBooks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await booksAPI.list({
        page, limit: 12,
        genre:  filters.genre  || undefined,
        format: filters.format || undefined,
        search: filters.search || undefined,
      });
      setBooks(data.books);
      setTotal(data.total);
      setPages(data.pages);
    } catch {
      setError('Error al cargar el catálogo. Inténtalo de nuevo.');
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => { fetchGenres(); }, [fetchGenres]);
  useEffect(() => { fetchBooks(); }, [fetchBooks]);

  function handleSearch(e) {
    e.preventDefault();
    setFilters((prev) => ({ ...prev, search: draftSearch }));
    setPage(1);
  }

  function handleGenreChange(e) {
    setFilters((prev) => ({ ...prev, genre: e.target.value }));
    setPage(1);
  }

  function handleFormatChange(e) {
    setFilters((prev) => ({ ...prev, format: e.target.value }));
    setPage(1);
  }

  function handleBookUpdate(updated) {
    setBooks((prev) => prev.map((b) => (b.id === updated.id ? { ...b, ...updated } : b)));
  }

  const hasFilters = filters.search || filters.genre || filters.format;

  return (
    <div className="py-8 min-h-[calc(100vh-64px)]">
      <div className="max-w-7xl mx-auto px-6">
        {/* Cabecera */}
        <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#1e3a5f]">Catálogo de libros</h1>
            <p className="text-slate-500 text-sm mt-0.5">{total} libros disponibles</p>
          </div>
        </div>

        {/* Filtros */}
        <form
          onSubmit={handleSearch}
          className="flex gap-3 flex-wrap bg-white p-4 rounded-xl border border-slate-200 shadow-sm mb-6"
        >
          <input
            className="border-2 border-slate-200 rounded-lg px-3 py-2 text-sm flex-1 min-w-[180px] focus:outline-none focus:border-[#1e3a5f] transition-colors"
            type="text"
            placeholder="Buscar por título o autor…"
            value={draftSearch}
            onChange={(e) => setDraftSearch(e.target.value)}
          />
          <select
            className="border-2 border-slate-200 rounded-lg px-3 py-2 text-sm flex-1 min-w-[160px] focus:outline-none focus:border-[#1e3a5f] transition-colors"
            value={filters.genre}
            onChange={handleGenreChange}
          >
            <option value="">Todas las categorías</option>
            {genres.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
          <select
            className="border-2 border-slate-200 rounded-lg px-3 py-2 text-sm flex-1 min-w-[140px] focus:outline-none focus:border-[#1e3a5f] transition-colors"
            value={filters.format}
            onChange={handleFormatChange}
          >
            <option value="">Todos los formatos</option>
            {formats.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <button type="submit" className="bg-[#1e3a5f] hover:bg-[#16304f] text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors">
            Buscar
          </button>
          {hasFilters && (
            <button
              type="button"
              className="border-2 border-[#1e3a5f] text-[#1e3a5f] hover:bg-[#1e3a5f] hover:text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
              onClick={() => { setFilters({ search: '', genre: '', format: '' }); setDraftSearch(''); setPage(1); }}
            >
              Limpiar
            </button>
          )}
        </form>

        {loading && <Spinner />}

        {!loading && error && (
          <div className="text-center py-16 text-slate-400">
            <div className="text-5xl mb-3">⚠️</div>
            <h3 className="text-lg font-semibold mb-1">Error al cargar</h3>
            <p className="text-sm mb-4">{error}</p>
            <button className="bg-[#1e3a5f] text-white font-semibold px-5 py-2 rounded-lg text-sm" onClick={fetchBooks}>
              Reintentar
            </button>
          </div>
        )}

        {!loading && !error && books.length === 0 && (
          <div className="text-center py-16 text-slate-400">
            <div className="text-5xl mb-3">🔍</div>
            <h3 className="text-lg font-semibold">No se encontraron libros</h3>
            <p className="text-sm mt-1">Prueba con otros filtros.</p>
          </div>
        )}

        {!loading && !error && books.length > 0 && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {books.map((book) => (
                <BookCard key={book.id} book={book} onUpdate={handleBookUpdate} />
              ))}
            </div>

            {pages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8 flex-wrap">
                <button
                  className="px-3 py-1.5 border-2 border-slate-200 rounded-lg text-sm hover:border-[#1e3a5f] hover:text-[#1e3a5f] transition-colors disabled:opacity-40 disabled:cursor-default"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  ← Anterior
                </button>
                {Array.from({ length: pages }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    className={`px-3 py-1.5 border-2 rounded-lg text-sm transition-colors ${
                      p === page
                        ? 'bg-[#1e3a5f] border-[#1e3a5f] text-white'
                        : 'border-slate-200 hover:border-[#1e3a5f] hover:text-[#1e3a5f]'
                    }`}
                    onClick={() => setPage(p)}
                  >
                    {p}
                  </button>
                ))}
                <button
                  className="px-3 py-1.5 border-2 border-slate-200 rounded-lg text-sm hover:border-[#1e3a5f] hover:text-[#1e3a5f] transition-colors disabled:opacity-40 disabled:cursor-default"
                  disabled={page === pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Siguiente →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
