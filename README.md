# SmartBooks 📚

Plataforma de recomendación personalizada de libros mediante Inteligencia Artificial.

**Proyecto del Curso de Especialización en Inteligencia Artificial y Big Data**  
**Autor:** Francisco Pedrosa Arjona

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Next.js 14 (API Routes) |
| Machine Learning | Python 3.11 + FastAPI + sentence-transformers |
| Base de datos | PostgreSQL 15 |
| Almacenamiento | MinIO (compatible S3) |
| Administración DB | pgweb |
| Contenedores | Docker + Docker Compose |
| Autenticación | JWT (JSON Web Tokens) |

---

## Arquitectura

```
┌──────────────────────────────────────────────────────┐
│                   Docker Compose                     │
│                                                      │
│  ┌─────────────┐      ┌────────────────────────┐    │
│  │  Frontend   │─────▶│  Backend (Next.js)     │    │
│  │  React/Vite │      │  API REST :3001         │    │
│  │  :3010      │      └───────┬────────────────┘    │
│  └─────────────┘              │                      │
│                       ┌───────┼──────────┐           │
│                       ▼       ▼          ▼           │
│                 ┌──────┐ ┌────────┐ ┌───────┐       │
│                 │  ML  │ │  PG    │ │ MinIO │       │
│                 │:8002 │ │:5433   │ │:9100  │       │
│                 └──────┘ └───┬────┘ └───────┘       │
│                              │                       │
│                         ┌────▼───┐                   │
│                         │ pgweb  │                   │
│                         │ :8082  │                   │
│                         └────────┘                   │
└──────────────────────────────────────────────────────┘
```

---

## Funcionalidades

- **Registro e inicio de sesión** con JWT
- **Catálogo de ~103 000 libros** (BooksDatasetClean) con búsqueda y filtrado por género
- **Sistema de likes**
- **Sistema de favoritos**
- **Valoración por estrellas** (1–5)
- **Recomendaciones personalizadas** mediante IA con estrategia adaptativa
- **Libros similares** para cualquier libro del catálogo
- **Perfil de usuario** con historial de interacciones y estadísticas
- **Administración de base de datos** vía pgweb

---

## Puesta en marcha

### Prerrequisitos

- Docker Desktop instalado y en ejecución
- Git
- Dataset `BooksDatasetClean.csv` en la raíz del repositorio

### 1. Clonar el repositorio

```bash
git clone https://github.com/pacopedrosa/smartBoooks.git
cd smartBoooks
```

### 2. Configurar variables de entorno

Crea el fichero `backend/.env` con el siguiente contenido:

```env
DATABASE_URL=postgresql://smartbooks:smartbooks_password@postgres:5432/smartbooks
JWT_SECRET=cambia_esto_por_un_secreto_seguro
MINIO_ENDPOINT=smartbooks-minio
MINIO_PORT=9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET=smartbooks
FRONTEND_URL=http://localhost:3010
ML_SERVICE_URL=http://ml-service:8000
```

### 3. Levantar todos los servicios

```bash
docker compose up --build
```

> El primer arranque puede tardar varios minutos: el servicio ML importa el dataset (~103 000 libros) y pre-calcula los embeddings semánticos de todos los libros en segundo plano.

### 4. Acceder a la aplicación

| Servicio | URL | Credenciales por defecto |
|----------|-----|--------------------------|
| Frontend | http://localhost:3010 | — |
| Backend API | http://localhost:3002 | — |
| ML Service | http://localhost:8002 | — |
| MinIO Console | http://localhost:9101 | `minioadmin` / `minioadmin123` |
| pgweb (DB admin) | http://localhost:8082 | — (acceso directo) |
| PostgreSQL | localhost:5433 | `smartbooks` / `smartbooks_password` |

---

## API REST — Endpoints principales

### Autenticación
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/register` | Registro de usuario |
| POST | `/api/auth/login` | Inicio de sesión |
| POST | `/api/auth/logout` | Cierre de sesión |

### Libros
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/books` | Listado paginado con búsqueda y filtro por género |
| GET | `/api/books/genres` | Lista de géneros disponibles |
| GET | `/api/books/:id` | Detalle de un libro |
| POST | `/api/books/:id/like` | Toggle like |
| POST | `/api/books/:id/favorite` | Toggle favorito |
| POST | `/api/books/:id/rate` | Valorar libro (1–5 ★) |
| GET | `/api/books/:id/similar` | Libros similares |

### Recomendaciones
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/recommendations` | Recomendaciones personalizadas |

### Perfil
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/users/profile` | Perfil + estadísticas |
| PUT | `/api/users/profile` | Actualizar nombre |

### Sistema
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/health` | Estado de los servicios |

---

## Algoritmos de recomendación

El motor de recomendación utiliza una **estrategia adaptativa** según el número de interacciones del usuario.

### Pesos de interacciones

| Interacción | Peso |
|-------------|------|
| Favorito | +2.0 |
| Like | +1.0 |
| Valoración 5★ | +3.0 |
| Valoración 4★ | +2.0 |
| Valoración 3★ | +1.0 |
| Valoración 1-2★ | ignorado |

### Estrategia adaptativa

| Interacciones | Algoritmo |
|---------------|-----------|
| 0 | Libros populares (más likes + favoritos) |
| 1–9 | Filtrado basado en contenido semántico (100%) |
| 10+ | Híbrido inteligente (CF si score ≥ 10% + contenido) |

### Filtrado basado en contenido (Content-Based)

Usa embeddings semánticos de **`sentence-transformers/all-MiniLM-L6-v2`** (384 dimensiones) sobre el texto combinado de **título + autor + género + descripción** de cada libro. Los embeddings se cachean en la columna `embedding FLOAT8[]` de PostgreSQL.

El perfil del usuario es la **media ponderada** de los embeddings de los libros con los que interactuó. Para recomendar, se calcula la similitud coseno entre el perfil y todos los libros del catálogo.

Se aplican dos boosts sobre la puntuación coseno base:

| Boost | Peso | Motivo |
|-------|------|--------|
| Author affinity | +45% máx. | Si leíste varios libros de un autor, sus otros libros suben en el ranking |
| Genre affinity | +20% máx. | Los géneros con más interacciones del usuario tienen prioridad |

### Filtrado colaborativo Item-Item (Collaborative Filtering)

Construye una matriz usuario-ítem con todas las interacciones del sistema y calcula la similitud coseno entre ítems. Solo se usa en el modo híbrido y **únicamente si el score es ≥ 0.10** — si la matriz es muy dispersa (pocos usuarios), este algoritmo genera ruido y se descarta automáticamente.

### Sistema híbrido inteligente

Con ≥ 10 interacciones se activa el modo híbrido:
1. Se evalúa la calidad del CF (score mínimo 0.10).
2. Si el CF tiene señal útil: hasta 50% CF + resto con contenido semántico.
3. Si el CF no aporta (base de datos dispersa): 100% contenido semántico.
4. Los scores finales se re-normalizan para que la UI siempre muestre porcentajes coherentes.

### Métrica de evaluación

El sistema se evalúa con **Leave-One-Out Hit Rate@10**:
- Se oculta la interacción más reciente de cada usuario (ground truth).
- Se generan recomendaciones con el historial restante.
- Se mide si el libro ocultado aparece en el Top-10.

| Versión | Dataset | Hit Rate@10 |
|---------|---------|-------------|
| v2 (actual) | BooksDatasetClean.csv — 103 000 libros, con descripción | **68%** |

---

## Dataset

El sistema usa **BooksDatasetClean.csv**, un dataset de Amazon Books con ~103 000 libros:

| Campo | Descripción |
|-------|-------------|
| Title | Título del libro |
| Authors | Autor(es) |
| Description | Sinopsis (68% de los libros la tienen, ~736 caracteres de media) |
| Category | Género / categoría |
| Publisher | Editorial |
| Price Starting With ($) | Precio en dólares |
| Publish Date (Year) | Año de publicación |

La descripción es clave para la calidad de los embeddings: permite al modelo entender el **contenido semántico real** del libro, no solo su título y género.

---

## Estructura del proyecto

```
smartBoooks/
├── docker-compose.yml
├── BooksDatasetClean.csv     # Dataset Amazon Books (~103 000 libros)
├── README.md
├── database/
│   └── init.sql              # Esquema PostgreSQL
├── ml-service/               # Servicio Python FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # Arranque + pre-cómputo de embeddings
│       ├── recommender.py    # Motor de recomendación híbrido
│       ├── seed.py           # Importación del dataset CSV
│       ├── database.py       # Conexión SQLAlchemy
│       └── schemas.py        # Modelos Pydantic
├── backend/                  # API REST Next.js
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── .env
│   ├── lib/
│   │   ├── db.js             # Pool de conexiones PostgreSQL
│   │   └── jwt.js            # Utilidades JWT
│   ├── middleware/
│   │   └── auth.js           # Middleware de autenticación
│   └── pages/api/
│       ├── health.js
│       ├── recommendations.js
│       ├── auth/             # register, login, logout
│       ├── books/            # CRUD + like, favorite, rate, similar
│       └── users/            # profile
├── frontend/                 # React + Vite
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── src/
│       ├── context/
│       │   └── AuthContext.jsx
│       ├── services/
│       │   └── api.js
│       ├── components/
│       │   ├── BookCard.jsx
│       │   ├── Navbar.jsx
│       │   └── ProtectedRoute.jsx
│       └── pages/
│           ├── Home.jsx
│           ├── Books.jsx
│           ├── Login.jsx
│           ├── Register.jsx
│           ├── Profile.jsx
│           └── Recommendations.jsx
└── scripts/
    └── seed_users.py         # Script para generar usuarios de prueba y medir métricas
```
