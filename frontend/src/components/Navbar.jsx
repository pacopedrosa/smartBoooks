import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  return (
    <nav className="sticky top-0 z-50 bg-[#1e3a5f] shadow-lg h-16">
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-full">
        <NavLink to="/" className="text-xl font-bold text-white flex items-center gap-2">
          📚 Smart<span className="text-amber-400">Books</span>
        </NavLink>

        {user && (
          <div className="flex items-center gap-2">
            {[
              { to: '/books',           label: 'Catálogo' },
              { to: '/recommendations', label: 'Para ti ✨' },
              { to: '/profile',         label: 'Perfil' },
            ].map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md text-sm transition-colors ${
                    isActive
                      ? 'bg-white/20 text-white'
                      : 'text-white/80 hover:bg-white/15 hover:text-white'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
            <button
              onClick={handleLogout}
              className="border border-white/40 text-white text-sm px-3 py-1.5 rounded-md hover:bg-white/15 transition-colors"
            >
              Salir
            </button>
          </div>
        )}

        {!user && (
          <div className="flex items-center gap-2">
            <NavLink to="/login"    className="text-white/80 hover:text-white px-3 py-1.5 rounded-md text-sm hover:bg-white/15 transition-colors">
              Iniciar sesión
            </NavLink>
            <NavLink to="/register" className="text-white/80 hover:text-white px-3 py-1.5 rounded-md text-sm hover:bg-white/15 transition-colors">
              Registrarse
            </NavLink>
          </div>
        )}
      </div>
    </nav>
  );
}
