# SmartBooks 📚

Plataforma de recomendación personalizada de libros mediante Inteligencia Artificial.

**Proyecto del Curso de Especialización en Inteligencia Artificial y Big Data**
**Autor:** Francisco Pedrosa Arjona

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 + Vite |
| Backend | Next.js 14 (API Routes) |
| Machine Learning | Python 3.11 + FastAPI + scikit-learn |
| Base de datos | PostgreSQL 15 |
| Almacenamiento | MinIO (compatible S3) |
| Contenedores | Docker + Docker Compose |
| Autenticación | JWT (JSON Web Tokens) |

## Arquitectura

```
┌───────────────────────────────────────────┐
│            Docker Compose                 │
│                                           │
│  ┌──────────┐     ┌──────────────────┐   │
│  │ Frontend │────▶│ Backend (Next.js) │   │
│  │  React   │     │   API REST 3001   │   │
│  │  :3000   │     └────────┬─────────┘   │
│  └──────────┘              │              │
│                    ┌───────┼───────┐      │
│                    ▼       ▼       ▼      │
│              ┌──────┐ ┌──────┐ ┌──────┐  │
│              │  ML  │ │  PG  │ │MinIO │  │
│              │:8000 │ │:5432 │ │:9000 │  │
│              └──────┘ └──────┘ └──────┘  │
└───────────────────────────────────────────┘
```

## Funcionalidades

- **Registro e inicio de sesión** con JWT
- **Catálogo de libros** con búsqueda y filtrado por género
- **Sistema de likes** (me gusta)
- **Sistema de favoritos**
- **Valoración por estrellas** (1–5)
- **Recomendaciones personalizadas** mediante IA:
  - Filtrado basado en contenido (TF-IDF)
  - Filtrado colaborativo (cosine similarity)
  - Sistema híbrido
- **Perfil de usuario** con historial de interacciones
- **Libros similares** por libro

## Puesta en marcha

### Prerrequisitos

- Docker Desktop instalado y en ejecución
- Git

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd smartBooks
```

### 2. Configurar variables de entorno

```bash
cp .env.example backend/.env
# Edita backend/.env y cambia JWT_SECRET por un valor seguro
```

### 3. Levantar todos los servicios

```bash
docker-compose up --build
```

### 4. Acceder a la aplicación

| Servicio | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:3001 |
| ML Service | http://localhost:8000 |
| MinIO Console | http://localhost:9001 |

---

## API REST — Endpoints principales

### Autenticación
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/register` | Registro de usuario |
| POST | `/api/auth/login` | Inicio de sesión |

### Libros
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/books` | Listado paginado con filtros |
| GET | `/api/books/genres` | Lista de géneros |
| GET | `/api/books/:id` | Detalle de un libro |
| POST | `/api/books/:id/like` | Toggle like |
| POST | `/api/books/:id/favorite` | Toggle favorito |
| POST | `/api/books/:id/rate` | Valorar libro |

### Recomendaciones
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/recommendations` | Recomendaciones personalizadas |

### Perfil
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/users/profile` | Perfil + estadísticas |
| PUT | `/api/users/profile` | Actualizar nombre |

---

## Algoritmos de recomendación

### Filtrado basado en contenido (Content-Based)
Utiliza **TF-IDF** sobre los metadatos de los libros (título, autor, género, descripción) para calcular la similitud coseno entre el perfil del usuario y todos los libros del catálogo. Se activa cuando el usuario tiene pocas interacciones.

### Filtrado colaborativo (Collaborative Filtering)
Construye una matriz usuario-ítem con las interacciones (likes y favoritos) y calcula la similitud coseno entre usuarios para encontrar patrones comunes. Se activa con suficientes interacciones.

### Sistema híbrido
Combina ambos enfoques: 50% filtrado colaborativo + 50% filtrado por contenido para obtener recomendaciones más precisas y diversas.

---

## Estructura del proyecto

```
smartBooks/
├── docker-compose.yml
├── .env.example
├── README.md
├── database/
│   └── init.sql           # Esquema y datos iniciales
├── ml-service/            # Servicio Python FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── recommender.py
│       ├── database.py
│       └── schemas.py
├── backend/               # API REST Next.js
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── .env
│   ├── lib/
│   │   ├── db.js
│   │   └── jwt.js
│   ├── middleware/
│   │   └── auth.js
│   └── pages/api/
│       ├── health.js
│       ├── recommendations.js
│       ├── auth/
│       ├── books/
│       └── users/
└── frontend/              # React + Vite
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    └── src/
        ├── context/
        ├── services/
        ├── components/
        └── pages/
```
