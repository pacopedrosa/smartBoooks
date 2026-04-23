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
- **Catálogo de ~32 000 libros** (Book Depository dataset) con búsqueda y filtrado por género
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
- Dataset `main_dataset.csv` en la raíz del repositorio

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
docker-compose up --build
```

> El primer arranque puede tardar varios minutos: el servicio ML descarga el modelo `all-MiniLM-L6-v2`, importa el dataset (~32 000 libros) y pre-calcula los embeddings semánticos en segundo plano.

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
| 0 | Libros populares (mejor valorados) |
| 1–9 | Filtrado basado en contenido (100%) |
| 10+ | Sistema híbrido (50% Item-Item CF + 50% contenido) |

### Filtrado basado en contenido (Content-Based)
Utiliza embeddings semánticos generados por **`sentence-transformers/all-MiniLM-L6-v2`** sobre el texto combinado de título, autor y géneros de cada libro. Los embeddings se cachean en la columna `embedding FLOAT8[]` de PostgreSQL para evitar recalcularlos. Se construye un perfil del usuario ponderando los embeddings de los libros con los que ha interactuado y se seleccionan los más similares por similitud coseno.

### Filtrado colaborativo Item-Item (Collaborative Filtering)
Construye una matriz ítem-usuario con todas las interacciones del sistema y calcula la similitud coseno entre ítems. Para cada libro con el que el usuario ha interactuado, encuentra los ítems más similares según los patrones de otros usuarios.

### Sistema híbrido
Combina ambas puntuaciones con igual peso: **50% Item-Item CF + 50% Content-Based**. Se activa automáticamente cuando el usuario tiene ≥ 10 interacciones y existen suficientes datos colaborativos.

---

## Estructura del proyecto

```
smartBoooks/
├── docker-compose.yml
├── main_dataset.csv          # Dataset Book Depository (~32 000 libros)
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
    └── seed_users.py         # Script para generar usuarios de prueba
```
