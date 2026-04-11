import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Register() {
  const { register } = useAuth();
  const navigate     = useNavigate();

  const [form,    setForm]    = useState({ name: '', email: '', password: '' });
  const [error,   setError]   = useState('');
  const [loading, setLoading] = useState(false);

  function handleChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError('');
  }

  function validate() {
    if (!form.name.trim())         return 'El nombre es obligatorio';
    if (!form.email.trim())        return 'El email es obligatorio';
    if (form.password.length < 8)  return 'La contraseña debe tener al menos 8 caracteres';
    return null;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const validationError = validate();
    if (validationError) { setError(validationError); return; }

    setLoading(true);
    setError('');
    try {
      await register(form.name, form.email, form.password);
      navigate('/books');
    } catch (err) {
      setError(err.response?.data?.error || 'Error al crear la cuenta');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#1e3a5f] to-[#2d6a9f] p-6">
      <div className="bg-white rounded-2xl shadow-2xl p-10 w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-extrabold text-[#1e3a5f]">
            📚 Smart<span className="text-amber-400">Books</span>
          </h1>
          <p className="text-slate-500 text-sm mt-1">Crea tu cuenta gratuita</p>
        </div>

        <form className="flex flex-col gap-5" onSubmit={handleSubmit} noValidate>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="name" className="text-sm font-semibold text-slate-700">Nombre</label>
            <input
              id="name" name="name" type="text"
              className="border-2 border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-[#1e3a5f] transition-colors"
              placeholder="Tu nombre"
              value={form.name} onChange={handleChange}
              required autoComplete="name"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="email" className="text-sm font-semibold text-slate-700">Email</label>
            <input
              id="email" name="email" type="email"
              className="border-2 border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-[#1e3a5f] transition-colors"
              placeholder="tu@email.com"
              value={form.email} onChange={handleChange}
              required autoComplete="email"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className="text-sm font-semibold text-slate-700">Contraseña</label>
            <input
              id="password" name="password" type="password"
              className="border-2 border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-[#1e3a5f] transition-colors"
              placeholder="Mínimo 8 caracteres"
              value={form.password} onChange={handleChange}
              required autoComplete="new-password"
            />
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#1e3a5f] hover:bg-[#16304f] text-white font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-55"
          >
            {loading ? 'Creando cuenta…' : 'Crear cuenta'}
          </button>
        </form>

        <p className="text-center text-sm text-slate-500 mt-6">
          ¿Ya tienes cuenta?{' '}
          <Link to="/login" className="text-[#1e3a5f] font-semibold hover:underline">
            Inicia sesión
          </Link>
        </p>
      </div>
    </div>
  );
}
