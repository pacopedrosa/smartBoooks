import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authAPI } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  // Al montar, recuperamos solo los datos del usuario (sin token)
  useEffect(() => {
    try {
      const stored = localStorage.getItem('sb_user');
      console.log('[AUTH] localStorage sb_user =', stored);
      if (stored) {
        const parsed = JSON.parse(stored);
        console.log('[AUTH] Usuario restaurado desde localStorage:', parsed);
        setUser(parsed);
      } else {
        console.log('[AUTH] No hay sesión guardada en localStorage');
      }
    } catch (e) {
      console.error('[AUTH] Error leyendo localStorage:', e);
      localStorage.removeItem('sb_user');
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (email, password) => {
    console.log('[AUTH] Intentando login para:', email);
    const { data } = await authAPI.login({ email, password });
    console.log('[AUTH] Login exitoso, usuario:', data.user);
    localStorage.setItem('sb_user', JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(async (name, email, password) => {
    console.log('[AUTH] Intentando registro para:', email);
    const { data } = await authAPI.register({ name, email, password });
    console.log('[AUTH] Registro exitoso, usuario:', data.user);
    localStorage.setItem('sb_user', JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      // Pide al backend que borre la cookie httpOnly
      await authAPI.logout();
    } catch {
      // Si falla la petición, limpiamos igualmente el estado local
    }
    localStorage.removeItem('sb_user');
    setUser(null);
  }, []);

  const updateUser = useCallback((updated) => {
    const merged = { ...user, ...updated };
    localStorage.setItem('sb_user', JSON.stringify(merged));
    setUser(merged);
  }, [user]);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
