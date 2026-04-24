"""
SmartBooks — Seed del dataset principal.

Carga BooksDatasetClean.csv (~103 000 filas) en la tabla `books`
usando inserciones por lotes.  Solo se ejecuta si la tabla está vacía para
evitar duplicados en reinicios de contenedor.

Columnas del CSV nuevo:
  Title, Authors, Description, Category, Publisher,
  Price Starting With ($), Publish Date (Month), Publish Date (Year)
"""

import logging
import os
import re

import pandas as pd
from sqlalchemy import text

from .database import engine

logger = logging.getLogger(__name__)

DATASET_PATH = os.getenv("DATASET_PATH", "/data/BooksDatasetClean.csv")
CHUNK_SIZE = 500


def _clean_author(raw: str) -> str:
    """
    Convierte "By Tolkien, J.R.R." → "J.R.R. Tolkien".
    Si el formato no coincide, devuelve la cadena original limpia.
    """
    if not raw or not isinstance(raw, str):
        return ""
    s = raw.strip()
    # Quitar prefijo "By "
    if s.lower().startswith("by "):
        s = s[3:].strip()
    # "Apellido, Nombre" → "Nombre Apellido"
    if "," in s:
        parts = s.split(",", 1)
        s = f"{parts[1].strip()} {parts[0].strip()}"
    return s.strip()


def _clean_category(raw: str) -> str:
    """
    Convierte " Fiction , General" → "Fiction-General".
    Elimina espacios extra y une subcategorías con guión.
    """
    if not raw or not isinstance(raw, str):
        return ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return "-".join(parts)


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
            conn.execute(text(
                "TRUNCATE TABLE ratings, favorites, likes, books RESTART IDENTITY CASCADE"
            ))

    logger.info("Iniciando seed desde '%s' …", DATASET_PATH)

    df = pd.read_csv(DATASET_PATH, dtype=str, keep_default_na=False)

    # Renombrar columnas al esquema interno
    df = df.rename(columns={
        "Title":                    "title",
        "Authors":                  "author",
        "Description":              "description",
        "Category":                 "genre",
        "Publisher":                "publisher",
        "Price Starting With ($)":  "price",
        "Publish Date (Year)":      "published_year",
    })

    # Limpiar autor y categoría
    df["author"]      = df["author"].apply(_clean_author).str[:500]
    df["genre"]       = df["genre"].apply(_clean_category).str[:300]
    df["title"]       = df["title"].str.strip()
    df["description"] = df.get("description", pd.Series(dtype=str)).str.strip()

    # Tipos numéricos
    df["price"]          = pd.to_numeric(df.get("price"),          errors="coerce")
    df["published_year"] = pd.to_numeric(df.get("published_year"), errors="coerce")

    # El nuevo CSV no tiene average_rating — se inicializa a 0
    df["average_rating"] = 0.0
    df["currency"]       = "$"

    # Columnas a insertar (las que existen en el DataFrame y en la BD)
    insert_cols = [
        "title", "author", "genre", "description",
        "price", "currency", "average_rating", "published_year",
    ]
    df = df[[c for c in insert_cols if c in df.columns]].copy()

    # Reemplazar cadenas vacías y NaN por None (NULL en Postgres)
    df = df.replace({"": None})
    df = df.where(pd.notnull(df), None)

    total_inserted = 0
    total_rows = len(df)

    with engine.begin() as conn:
        for start in range(0, total_rows, CHUNK_SIZE):
            chunk = df.iloc[start: start + CHUNK_SIZE]
            rows = chunk.to_dict(orient="records")
            conn.execute(
                text(
                    """
                    INSERT INTO books
                        (title, author, genre, description,
                         price, currency, average_rating, published_year)
                    VALUES
                        (:title, :author, :genre, :description,
                         :price, :currency, :average_rating, :published_year)
                    """
                ),
                rows,
            )
            total_inserted += len(rows)
            logger.info(
                "  Seed progreso: %d / %d filas", total_inserted, total_rows
            )

    logger.info("Seed completado: %d libros cargados.", total_inserted)
