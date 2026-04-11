import { useState, useEffect } from 'react';
import { userAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';

function Spinner() {
  return (
    <div className="flex justify-center py-16">
      <div className="w-10 h-10 border-4 border-slate-200 border-t-[#1e3a5f] rounded-full animate-spin-custom" />
    </div>
  );
}

export default function Profile() {
  const { user, updateUser } = useAuth();

  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  const [editing, setEditing] = useState(false);
  const [newName, setNewName] = useState('');
  const [saving,  setSaving]  = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const { data } = await userAPI.profile();
        setProfile(data);
        setNewName(data.user.name);
      } catch {
        setError('Error al cargar el perfil.');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleSaveName(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    setSaving(true);
    setSaveMsg('');
    try {
      const { data } = await userAPI.updateProfile({ name: newName.trim() });
      updateUser(data.user);
      setProfile((prev) => ({ ...prev, user: { ...prev.user, name: data.user.name } }));
      setEditing(false);
      setSaveMsg('Nombre actualizado correctamente.');
      setTimeout(() => setSaveMsg(''), 3000);
    } catch {
      setSaveMsg('Error al actualizar el nombre.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="py-8"><div className="max-w-4xl mx-auto px-6"><Spinner /></div></div>;
  if (error)   return (
    <div className="py-8"><div className="max-w-4xl mx-auto px-6 text-center py-16 text-slate-400">
      <div className="text-5xl mb-3">⚠️</div>
      <h3 className="text-lg font-semibold">{error}</h3>
    </div></div>
  );

  const { stats, liked_books, favorite_books } = profile;
  const initial = (profile.user.name?.[0] || 'U').toUpperCase();

  return (
    <div className="py-8 min-h-[calc(100vh-64px)]">
      <div className="max-w-4xl mx-auto px-6">

        {/* Cabecera de perfil */}
        <div className="bg-gradient-to-br from-[#1e3a5f] to-[#2d6a9f] text-white p-8 rounded-2xl flex flex-wrap items-center gap-6 mb-8">
          <div className="w-20 h-20 rounded-full bg-amber-400 flex items-center justify-center text-3xl font-bold text-white flex-shrink-0">
            {initial}
          </div>
          <div className="flex-1 min-w-0">
            {editing ? (
              <form onSubmit={handleSaveName} className="flex flex-wrap gap-2 mb-1">
                <input
                  className="bg-white/20 text-white border border-white/40 rounded-lg px-3 py-1.5 text-sm focus:outline-none placeholder-white/60"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  autoFocus
                />
                <button type="submit" disabled={saving} className="bg-amber-400 hover:bg-amber-500 text-white text-sm font-semibold px-3 py-1.5 rounded-lg transition-colors disabled:opacity-55">
                  {saving ? 'Guardando…' : 'Guardar'}
                </button>
                <button type="button" onClick={() => setEditing(false)} className="border border-white/40 text-white text-sm px-3 py-1.5 rounded-lg hover:bg-white/15 transition-colors">
                  Cancelar
                </button>
              </form>
            ) : (
              <h2 className="text-xl font-bold mb-0.5">
                {profile.user.name}
                <button
                  onClick={() => setEditing(true)}
                  className="ml-2 text-white/60 hover:text-white text-base bg-transparent border-0 cursor-pointer"
                  title="Editar nombre"
                >
                  ✏️
                </button>
              </h2>
            )}
            <p className="text-white/80 text-sm">{profile.user.email}</p>
            <p className="text-white/60 text-xs mt-0.5">
              Miembro desde {new Date(profile.user.created_at).toLocaleDateString('es-ES')}
            </p>

            {/* Estadísticas */}
            <div className="flex gap-6 mt-4 flex-wrap">
              {[
                { value: stats.total_likes,     label: 'Likes' },
                { value: stats.total_favorites, label: 'Favoritos' },
                { value: stats.total_rated,     label: 'Valorados' },
              ].map(({ value, label }) => (
                <div key={label} className="text-center">
                  <div className="text-2xl font-bold text-amber-400">{value}</div>
                  <div className="text-xs text-white/70">{label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {saveMsg && (
          <div className="bg-green-50 border border-green-200 text-green-700 text-sm font-medium rounded-lg px-4 py-2.5 mb-5">
            {saveMsg}
          </div>
        )}

        {/* Libros con like */}
        <section className="mb-8">
          <h2 className="text-lg font-bold text-[#1e3a5f] pb-2 border-b-2 border-slate-200 mb-4">
            ❤️ Libros que me gustan ({liked_books.length})
          </h2>
          {liked_books.length === 0 ? (
            <p className="text-slate-400 text-sm">Aún no has dado like a ningún libro.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {liked_books.map((b) => (
                <div key={b.id} className="bg-white rounded-lg border border-slate-200 p-3">
                  <p className="text-sm font-semibold leading-tight line-clamp-2">{b.title}</p>
                  <p className="text-xs text-slate-400 mt-1">{b.author}</p>
                  {b.genre && (
                    <span className="mt-1.5 inline-block bg-blue-50 text-[#1e3a5f] text-[11px] font-semibold px-1.5 py-0.5 rounded">
                      {b.genre}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Favoritos */}
        <section className="mb-8">
          <h2 className="text-lg font-bold text-[#1e3a5f] pb-2 border-b-2 border-slate-200 mb-4">
            🔖 Mis favoritos ({favorite_books.length})
          </h2>
          {favorite_books.length === 0 ? (
            <p className="text-slate-400 text-sm">Aún no tienes libros favoritos.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {favorite_books.map((b) => (
                <div key={b.id} className="bg-white rounded-lg border border-slate-200 p-3">
                  <p className="text-sm font-semibold leading-tight line-clamp-2">{b.title}</p>
                  <p className="text-xs text-slate-400 mt-1">{b.author}</p>
                  {b.genre && (
                    <span className="mt-1.5 inline-block bg-blue-50 text-[#1e3a5f] text-[11px] font-semibold px-1.5 py-0.5 rounded">
                      {b.genre}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
