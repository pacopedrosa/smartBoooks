"""
SmartBooks — Seed del dataset principal.

Carga main_dataset.csv (Book Depository, ~32 000 filas) en la tabla `books`
usando inserciones por lotes.  Solo se ejecuta si la tabla está vacía para
evitar duplicados en reinicios de contenedor.
"""

import logging
import os

import pandas as pd
from sqlalchemy import text

from .database import engine

logger = logging.getLogger(__name__)

DATASET_PATH = os.getenv("DATASET_PATH", "/data/main_dataset.csv")
CHUNK_SIZE = 500

# Mapeo columna CSV → columna DB
COLUMN_MAP = {
    "image":                 "cover_url",
    "name":                  "title",
    "author":                "author",
    "format":                "format",
    "book_depository_stars": "average_rating",
    "price":                 "price",
    "currency":              "currency",
    "old_price":             "old_price",
    "isbn":                  "isbn",
    "category":              "genre",
}


def seed_books() -> None:
    """
    Inserta todos los libros del CSV si la tabla `books` está vacía.
    Opera en chunks para no saturar memoria ni conexión.
    """
    if not os.path.exists(DATASET_PATH):
        logger.warning(
            "Dataset no encontrado en '%s' — seed omitido.  "
            "Monta el archivo como volumen en docker-compose.",
            DATASET_PATH,
        )
        return

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM books")).scalar() or 0

    # Si ya hay un seed completo (≥10 000 filas) no repetir.
    # Si hay filas pero pocas (e.g. datos hardcodeados del init.sql antiguo),
    # se trunca y se recarga el dataset completo.
    if count >= 10_000:
        logger.info(
            "La tabla 'books' ya contiene %d filas — seed omitido.", count
        )
        return

    if count > 0:
        logger.info(
            "La tabla 'books' tiene solo %d filas (datos parciales). "
            "Truncando y recargando el dataset completo…",
            count,
        )
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE ratings, favorites, likes, books RESTART IDENTITY CASCADE"))

    logger.info("Iniciando seed desde '%s' …", DATASET_PATH)

    df = pd.read_csv(DATASET_PATH, dtype=str, keep_default_na=False)
    df = df.rename(columns=COLUMN_MAP)

    # Conservar solo las columnas que existen en el CSV
    keep_cols = [col for col in COLUMN_MAP.values() if col in df.columns]
    df = df[keep_cols].copy()

    # Limpiar y convertir tipos
    df["title"]  = df["title"].str.strip()
    df["author"] = df.get("author", pd.Series(dtype=str)).str.strip()
    df["genre"]  = df.get("genre",  pd.Series(dtype=str)).str.strip()

    df["average_rating"] = pd.to_numeric(
        df.get("average_rating"), errors="coerce"
    ).fillna(0.0)
    df["price"]     = pd.to_numeric(df.get("price"),     errors="coerce")
    df["old_price"] = pd.to_numeric(df.get("old_price"), errors="coerce")

    # Reemplazar cadenas vacías y NaN por None (NULL en Postgres)
    df = df.replace({"": None})
    df = df.where(pd.notnull(df), None)

    total_inserted = 0
    total_rows = len(df)

    with engine.begin() as conn:
        for start in range(0, total_rows, CHUNK_SIZE):
            chunk = df.iloc[start : start + CHUNK_SIZE]
            rows = chunk.to_dict(orient="records")
            conn.execute(
                text(
                    """
                    INSERT INTO books
                        (title, author, genre, format, cover_url,
                         isbn, average_rating, price, currency, old_price)
                    VALUES
                        (:title, :author, :genre, :format, :cover_url,
                         :isbn, :average_rating, :price, :currency, :old_price)
                    """
                ),
                rows,
            )
            total_inserted += len(rows)
            logger.info(
                "  Seed progreso: %d / %d filas", total_inserted, total_rows
            )

    logger.info("Seed completado: %d libros cargados.", total_inserted)
