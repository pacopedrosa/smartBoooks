"""
SmartBooks — Motor de recomendación de libros.

Estrategia híbrida:
  - Cold start (0 interacciones): libros mejor valorados por rating.
  - Pocos datos (1-4 interacciones): filtrado basado en contenido (TF-IDF).
  - Datos suficientes (5+): sistema híbrido (colaborativo + contenido).
"""

import logging
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de base de datos
# ---------------------------------------------------------------------------

def _get_user_interactions(db: Session, user_id: int) -> Tuple[List[int], List[int]]:
    """Devuelve (liked_ids, favorited_ids) para un usuario."""
    liked = [
        row[0] for row in db.execute(
            text("SELECT book_id FROM likes WHERE user_id = :uid"),
            {"uid": user_id}
        ).fetchall()
    ]
    favorited = [
        row[0] for row in db.execute(
            text("SELECT book_id FROM favorites WHERE user_id = :uid"),
            {"uid": user_id}
        ).fetchall()
    ]
    return liked, favorited


def _get_all_books(db: Session) -> pd.DataFrame:
    """Recupera todos los libros con campos enriquecidos del dataset."""
    rows = db.execute(
        text(
            "SELECT id, title, author, genre, format, cover_url, "
            "price, currency, average_rating "
            "FROM books ORDER BY id"
        )
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(
        rows,
        columns=["id", "title", "author", "genre", "format",
                 "cover_url", "price", "currency", "average_rating"]
    )


def _build_features(df: pd.DataFrame) -> "pd.Series[str]":
    """
    Texto de características para TF-IDF.
    El título se repite 3 veces para darle mayor peso semántico.
    No hay descripción en el dataset, se usan titulo, autor, género y formato.
    """
    t = df["title"].fillna("")
    return (
        t + " " + t + " " + t + " " +
        df["author"].fillna("") + " " +
        df["genre"].fillna("") + " " +
        df["format"].fillna("")
    )


def _books_by_ids(db: Session, book_ids: List[int]) -> List:
    """
    Recupera filas de libros por lista de IDs preservando el orden original.
    Construye el IN con literales enteros (seguros, son IDs del sistema).
    """
    if not book_ids:
        return []
    safe_ids = [int(bid) for bid in book_ids]
    id_literal = "(" + ",".join(str(i) for i in safe_ids) + ")"
    rows = db.execute(
        text(
            "SELECT id, title, author, genre, format, cover_url, price, currency "
            f"FROM books WHERE id IN {id_literal}"
        )
    ).fetchall()
    rows_by_id = {row[0]: row for row in rows}
    return [rows_by_id[bid] for bid in safe_ids if bid in rows_by_id]


# ---------------------------------------------------------------------------
# Algoritmo 1: Filtrado basado en contenido (TF-IDF)
# ---------------------------------------------------------------------------

def content_based_recommendations(
    db: Session, user_id: int, limit: int = 10
) -> List[Dict]:
    """
    Recomendaciones por similitud de contenido TF-IDF.
    Cold start: top-N libros ordenados por average_rating DESC.
    Con interacciones: media vectorial del perfil del usuario.
    """
    liked, favorited = _get_user_interactions(db, user_id)
    interacted = list(set(liked + favorited))

    all_books = _get_all_books(db)
    if all_books.empty:
        return []

    # Cold start — top libros por rating del dataset
    if not interacted:
        sample = (
            all_books
            .sort_values("average_rating", ascending=False)
            .head(limit)
        )
        return [
            {
                "book_id":   int(row["id"]),
                "title":     row["title"],
                "author":    row["author"],
                "genre":     row["genre"],
                "cover_url": row["cover_url"],
                "price":     float(row["price"]) if row["price"] is not None else None,
                "currency":  row["currency"],
                "score":     round(float(row["average_rating"]) / 5.0, 4),
                "reason":    "Mejor valorado por la comunidad",
            }
            for _, row in sample.iterrows()
        ]

    all_books = all_books.copy()
    all_books["features"] = _build_features(all_books)

    tfidf = TfidfVectorizer(max_features=5000, sublinear_tf=True)
    try:
        tfidf_matrix = tfidf.fit_transform(all_books["features"])
    except Exception as exc:
        logger.error("TF-IDF error: %s", exc)
        return []

    interacted_idx = all_books.index[all_books["id"].isin(interacted)].tolist()
    if not interacted_idx:
        return []

    user_profile = np.mean(
        tfidf_matrix[interacted_idx].toarray(), axis=0
    ).reshape(1, -1)

    scores = cosine_similarity(user_profile, tfidf_matrix).flatten()
    all_books["score"] = scores

    candidates = (
        all_books[~all_books["id"].isin(interacted)]
        .sort_values("score", ascending=False)
        .head(limit)
    )

    return [
        {
            "book_id":   int(row["id"]),
            "title":     row["title"],
            "author":    row["author"],
            "genre":     row["genre"],
            "cover_url": row["cover_url"],
            "price":     float(row["price"]) if row["price"] is not None else None,
            "currency":  row["currency"],
            "score":     round(float(row["score"]), 4),
            "reason":    f"Similar a los libros que te gustan de {row['author']}",
        }
        for _, row in candidates.iterrows()
    ]


# ---------------------------------------------------------------------------
# Algoritmo 2: Filtrado colaborativo (User-User)
# ---------------------------------------------------------------------------

def collaborative_filtering(
    db: Session, user_id: int, limit: int = 10
) -> List[Dict]:
    """
    Filtrado colaborativo User-User con similitud coseno.
    likes = peso 1, favoritos = peso 2.
    """
    rows = db.execute(
        text(
            "SELECT user_id, book_id, 1 AS w FROM likes "
            "UNION ALL "
            "SELECT user_id, book_id, 2 AS w FROM favorites"
        )
    ).fetchall()

    if not rows:
        return []

    df = pd.DataFrame(rows, columns=["user_id", "book_id", "w"])

    if user_id not in df["user_id"].values:
        return []

    matrix = df.pivot_table(
        index="user_id", columns="book_id", values="w", fill_value=0
    )

    if user_id not in matrix.index:
        return []

    sim_matrix = cosine_similarity(matrix)
    sim_df = pd.DataFrame(sim_matrix, index=matrix.index, columns=matrix.index)

    similar_users = (
        sim_df[user_id].drop(labels=[user_id]).sort_values(ascending=False).head(10)
    )

    if similar_users.empty:
        return []

    user_books = set(df.loc[df["user_id"] == user_id, "book_id"].tolist())
    top_users = similar_users[similar_users > 0].index.tolist()

    if not top_users:
        return []

    candidate_books = df[
        df["user_id"].isin(top_users) & ~df["book_id"].isin(user_books)
    ]["book_id"].value_counts()

    if candidate_books.empty:
        return []

    top_book_ids = candidate_books.head(limit).index.tolist()
    book_rows = _books_by_ids(db, top_book_ids)

    max_count = float(candidate_books.max())
    result = []
    for row in book_rows:
        score = round(float(candidate_books.get(row[0], 1)) / max_count, 4)
        result.append(
            {
                "book_id":   row[0],
                "title":     row[1],
                "author":    row[2],
                "genre":     row[3],
                "cover_url": row[5],
                "price":     float(row[6]) if row[6] is not None else None,
                "currency":  row[7],
                "score":     score,
                "reason":    "Usuarios con gustos similares también leyeron este libro",
            }
        )

    return sorted(result, key=lambda x: x["score"], reverse=True)


# ---------------------------------------------------------------------------
# Recomendador híbrido principal
# ---------------------------------------------------------------------------

def get_recommendations(db: Session, user_id: int, limit: int = 10) -> Dict:
    """
    Sistema híbrido de recomendación.
      - 0 interacciones  → popular (rating DESC)
      - 1-4              → content-based (TF-IDF)
      - 5+               → hybrid (50% colaborativo + 50% contenido)
    """
    liked, favorited = _get_user_interactions(db, user_id)
    total_interactions = len(set(liked + favorited))

    if total_interactions == 0:
        recs = content_based_recommendations(db, user_id, limit)
        algorithm = "popular"

    elif total_interactions < 5:
        recs = content_based_recommendations(db, user_id, limit)
        algorithm = "content-based"

    else:
        cb_recs = content_based_recommendations(db, user_id, limit)
        cf_recs = collaborative_filtering(db, user_id, limit)

        if cf_recs:
            seen: set = set()
            merged: List[Dict] = []

            for rec in cf_recs[: limit // 2]:
                if rec["book_id"] not in seen:
                    seen.add(rec["book_id"])
                    merged.append(rec)

            for rec in cb_recs:
                if rec["book_id"] not in seen and len(merged) < limit:
                    seen.add(rec["book_id"])
                    merged.append(rec)

            recs = merged
            algorithm = "hybrid"
        else:
            recs = cb_recs
            algorithm = "content-based"

    return {
        "user_id":        user_id,
        "recommendations": recs[:limit],
        "algorithm":      algorithm,
        "total":          len(recs[:limit]),
    }


# ---------------------------------------------------------------------------
# Libros similares (sin contexto de usuario)
# ---------------------------------------------------------------------------

def get_similar_books(db: Session, book_id: int, limit: int = 5) -> List[Dict]:
    """Devuelve libros similares al indicado usando similitud TF-IDF."""
    all_books = _get_all_books(db)
    if all_books.empty or book_id not in all_books["id"].values:
        return []

    all_books = all_books.copy()
    all_books["features"] = _build_features(all_books)

    tfidf = TfidfVectorizer(max_features=5000, sublinear_tf=True)
    try:
        tfidf_matrix = tfidf.fit_transform(all_books["features"])
    except Exception as exc:
        logger.error("TF-IDF similar books error: %s", exc)
        return []

    idx = all_books.index[all_books["id"] == book_id][0]
    scores = cosine_similarity(tfidf_matrix[idx], tfidf_matrix).flatten()
    all_books = all_books.copy()
    all_books["score"] = scores

    similar = (
        all_books[all_books["id"] != book_id]
        .sort_values("score", ascending=False)
        .head(limit)
    )

    return [
        {
            "book_id":   int(row["id"]),
            "title":     row["title"],
            "author":    row["author"],
            "genre":     row["genre"],
            "cover_url": row["cover_url"],
            "score":     round(float(row["score"]), 4),
        }
        for _, row in similar.iterrows()
    ]
