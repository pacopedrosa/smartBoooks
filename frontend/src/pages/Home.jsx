import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const FEATURES = [
  { icon: '🤖', title: 'IA personalizada',  desc: 'Algoritmos de aprendizaje automático que aprenden de tus gustos.' },
  { icon: '❤️', title: 'Likes y favoritos', desc: 'Marca los libros que te gustan y guarda tus favoritos.' },
  { icon: '⭐', title: 'Valoraciones',       desc: 'Puntúa libros del 1 al 5 para mejorar tus recomendaciones.' },
  { icon: '📚', title: 'Amplio catálogo',    desc: '25 libros iniciales en múltiples géneros, con más por llegar.' },
];

export default function Home() {
  const { user } = useAuth();

  return (
    <>
      {/* Hero */}
      <section className="bg-gradient-to-br from-[#1e3a5f] to-[#2d6a9f] text-white py-20 text-center">
        <div className="max-w-3xl mx-auto px-6">
          <h1 className="text-4xl md:text-5xl font-extrabold mb-4">
            Smart<span className="text-amber-400">Books</span>
          </h1>
          <p className="text-lg text-white/90 mb-8 max-w-xl mx-auto">
            Descubre tu próxima lectura perfecta gracias a la Inteligencia Artificial.
            Cuanto más interactúas, mejores recomendaciones recibes.
          </p>
          <div className="flex gap-4 justify-center flex-wrap">
            {user ? (
              <>
                <Link to="/books"           className="bg-amber-400 hover:bg-amber-500 text-white font-bold px-6 py-3 rounded-lg transition-colors">Ver catálogo</Link>
                <Link to="/recommendations" className="border-2 border-white text-white font-bold px-6 py-3 rounded-lg hover:bg-white/15 transition-colors">Mis recomendaciones ✨</Link>
              </>
            ) : (
              <>
                <Link to="/register" className="bg-amber-400 hover:bg-amber-500 text-white font-bold px-6 py-3 rounded-lg transition-colors">Comenzar gratis</Link>
                <Link to="/login"    className="border-2 border-white text-white font-bold px-6 py-3 rounded-lg hover:bg-white/15 transition-colors">Iniciar sesión</Link>
              </>
            )}
          </div>
        </div>
      </section>

      {/* Features */}
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 my-12">
          {FEATURES.map((f) => (
            <div key={f.title} className="bg-white rounded-xl p-6 shadow-md text-center">
              <div className="text-4xl mb-3">{f.icon}</div>
              <h3 className="font-bold text-[#1e3a5f] mb-2">{f.title}</h3>
              <p className="text-sm text-slate-500">{f.desc}</p>
            </div>
          ))}
        </div>

        <div className="text-center pb-16">
          <h2 className="text-2xl font-bold text-[#1e3a5f] mb-3">¿Cómo funciona?</h2>
          <p className="text-slate-500 max-w-xl mx-auto mb-6 text-sm leading-relaxed">
            SmartBooks analiza tus interacciones (likes, favoritos y valoraciones) para generar
            recomendaciones únicas mediante filtrado basado en contenido (TF-IDF) y filtrado
            colaborativo. Con más interacciones, el sistema híbrido combina ambos enfoques.
          </p>
          {!user && (
            <Link to="/register" className="bg-[#1e3a5f] hover:bg-[#16304f] text-white font-bold px-6 py-3 rounded-lg transition-colors">
              Crear cuenta gratuita
            </Link>
          )}
        </div>
      </div>
    </>
  );
}
