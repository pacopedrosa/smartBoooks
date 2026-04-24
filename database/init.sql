-- ============================================================
-- SmartBooks — Esquema de base de datos
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS books (
    id             SERIAL PRIMARY KEY,
    title          VARCHAR(600) NOT NULL,
    author         TEXT,
    genre          TEXT,
    format         VARCHAR(50),
    description    TEXT,
    cover_url      VARCHAR(1000),
    isbn           VARCHAR(20),
    published_year INTEGER,
    pages          INTEGER,
    language       VARCHAR(50) DEFAULT 'English',
    price          DECIMAL(10,2),
    currency       VARCHAR(5)  DEFAULT '$',
    old_price      DECIMAL(10,2),
    average_rating DECIMAL(3,2) DEFAULT 0,
    total_ratings  INTEGER DEFAULT 0,
    embedding      FLOAT8[],
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS likes (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    book_id    INTEGER REFERENCES books(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, book_id)
);

CREATE TABLE IF NOT EXISTS favorites (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    book_id    INTEGER REFERENCES books(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, book_id)
);

CREATE TABLE IF NOT EXISTS ratings (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    book_id    INTEGER REFERENCES books(id) ON DELETE CASCADE,
    rating     INTEGER CHECK (rating >= 1 AND rating <= 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, book_id)
);

-- ============================================================
-- Índices para optimizar consultas frecuentes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_likes_user_id    ON likes(user_id);
CREATE INDEX IF NOT EXISTS idx_likes_book_id    ON likes(book_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user   ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_book   ON favorites(book_id);
CREATE INDEX IF NOT EXISTS idx_ratings_user     ON ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_book     ON ratings(book_id);
CREATE INDEX IF NOT EXISTS idx_books_genre      ON books(genre);

-- Migración segura: añadir columna si el volumen ya existía
ALTER TABLE books ADD COLUMN IF NOT EXISTS embedding FLOAT8[];

-- ============================================================
-- Los libros se cargan desde main_dataset.csv al levantar
-- el servicio ml-service (ver ml-service/app/seed.py).
-- ============================================================
