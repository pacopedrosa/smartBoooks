import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  console.log('[PROTECTED] loading:', loading, '| user:', user);

  if (loading) {
    console.log('[PROTECTED] Mostrando spinner (cargando sesión)');
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-10 h-10 border-4 border-slate-200 border-t-[#1e3a5f] rounded-full animate-spin-custom" />
      </div>
    );
  }

  if (!user) {
    console.warn('[PROTECTED] No hay usuario — redirigiendo a /login');
    return <Navigate to="/login" replace />;
  }

  console.log('[PROTECTED] Acceso permitido para:', user.email);
  return children;
}
