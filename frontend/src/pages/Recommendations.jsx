import { useState, useEffect } from 'react';
import { recsAPI } from '../services/api';

const ALGO_LABELS = {
  popular:         { label: 'Libros populares',       icon: '🔥' },
  'content-based': { label: 'Basado en tus gustos',   icon: '🎯' },
  hybrid:          { label: 'Sistema híbrido IA',      icon: '🤖' },
};

function Spinner() {
  return (
    <div className="flex justify-center py-16">
      <div className="w-10 h-10 border-4 border-slate-200 border-t-[#1e3a5f] rounded-full animate-spin-custom" />
    </div>
  );
}

export default function Recommendations() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');
  const [limit,   setLimit]   = useState(10);

  async function fetchRecs(l = limit) {
    setLoading(true);
    setError('');
    try {
      const { data: res } = await recsAPI.get(l);
      setData(res);
    } catch (err) {
      setError(err.response?.data?.error || 'Error al obtener recomendaciones. Asegúrate de que el servicio ML está activo.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchRecs(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const algo = data ? (ALGO_LABELS[data.algorithm] || { label: data.algorithm, icon: '📊' }) : null;

  return (
    <div className="py-8 min-h-[calc(100vh-64px)]">
      <div className="max-w-2xl mx-auto px-6">
        {/* Cabecera */}
        <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#1e3a5f]">Recomendaciones para ti ✨</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              Generadas por inteligencia artificial a partir de tus interacciones
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="border-2 border-slate-200 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:border-[#1e3a5f]"
              value={limit}
              onChange={(e) => { setLimit(+e.target.value); fetchRecs(+e.target.value); }}
            >
              {[5, 10, 15, 20].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            <button
              onClick={() => fetchRecs()}
              className="bg-[#1e3a5f] hover:bg-[#16304f] text-white font-semibold text-sm px-4 py-1.5 rounded-lg transition-colors"
            >
              Actualizar
            </button>
          </div>
        </div>

        {loading && <Spinner />}

        {!loading && error && (
          <div className="text-center py-16 text-slate-400">
            <div className="text-5xl mb-3">⚠️</div>
            <h3 className="text-lg font-semibold text-slate-600">No se pudieron cargar las recomendaciones</h3>
            <p className="text-sm mt-1 mb-4">{error}</p>
            <button
              className="bg-[#1e3a5f] text-white font-semibold px-5 py-2 rounded-lg text-sm"
              onClick={() => fetchRecs()}
            >
              Reintentar
            </button>
          </div>
        )}

        {!loading && data && (
          <>
            {/* Badge de algoritmo */}
            <div className="inline-flex items-center gap-2 bg-gradient-to-r from-[#1e3a5f] to-[#2d6a9f] text-white text-sm px-4 py-1.5 rounded-full mb-5">
              <span>{algo.icon}</span>
              <span>Algoritmo: <strong>{algo.label}</strong></span>
              <span className="opacity-70">· {data.total} recomendaciones</span>
            </div>

            {data.recommendations.length === 0 ? (
              <div className="text-center py-16 text-slate-400">
                <div className="text-5xl mb-3">📚</div>
                <h3 className="text-lg font-semibold">Aún no tenemos recomendaciones</h3>
                <p className="text-sm mt-1">Dale like a algunos libros del catálogo para empezar.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {data.recommendations.map((rec, i) => (
                  <div key={rec.book_id} className="bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow flex gap-4 p-4 items-start">
                    {/* Portada real del libro */}
                    <div className="w-16 min-w-16 aspect-[2/3] rounded-lg bg-gradient-to-br from-slate-100 to-slate-200 overflow-hidden flex-shrink-0">
                      {rec.cover_url ? (
                        <img
                          src={rec.cover_url}
                          alt={rec.title}
                          loading="lazy"
                          className="w-full h-full object-cover"
                          onError={(e) => { e.currentTarget.style.display = 'none'; }}
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-2xl">📖</div>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start gap-2 flex-wrap">
                        <div>
                          <p className="font-bold text-sm leading-tight">{i + 1}. {rec.title}</p>
                          <p className="text-xs text-slate-500 mt-0.5">{rec.author}</p>
                        </div>
                        {rec.genre && (
                          <span className="bg-blue-50 text-[#1e3a5f] text-[11px] font-semibold px-2 py-0.5 rounded whitespace-nowrap flex-shrink-0">
                            {rec.genre}
                          </span>
                        )}
                      </div>
                      <span className="inline-block mt-2 text-[11px] bg-blue-50 text-[#1e3a5f] px-2 py-0.5 rounded">
                        {rec.reason}
                      </span>
                      <div className="flex items-center gap-3 mt-1.5">
                        <p className="text-[11px] text-slate-400">
                          Relevancia: <strong>{(rec.score * 100).toFixed(1)}%</strong>
                        </p>
                        {rec.price != null && (
                          <p className="text-[11px] font-bold text-[#1e3a5f]">
                            {rec.currency ?? '$'}{Number(rec.price).toFixed(2)}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
