"""
SmartBooks — Motor de recomendación de libros.

Estrategia híbrida:
  - Cold start (0 interacciones): libros mejor valorados por rating.
  - Pocos datos (1-4 interacciones): filtrado basado en contenido (TF-IDF).
  - Datos suficientes (5+): sistema híbrido (colaborativo + contenido).
"""

import logging
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Modelo singleton — se carga una sola vez al arrancar el servicio
_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Cargando modelo sentence-transformers (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Modelo cargado correctamente.")
    return _model


# ---------------------------------------------------------------------------
# Helpers de base de datos
# ---------------------------------------------------------------------------

def _get_user_interactions(db: Session, user_id: int) -> Dict[int, float]:
    """
    Devuelve un dict {book_id: weight} con todas las interacciones del usuario.

    Pesos:
      - Favorito   : +2.0
      - Like       : +1.0
      - Rating 5★  : +3.0
      - Rating 4★  : +2.0
      - Rating 3★  : +1.0
      - Rating 1-2★: ignorado (negativo, no aporta al perfil positivo)
    """
    weights: Dict[int, float] = {}

    for row in db.execute(
        text("SELECT book_id FROM likes WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchall():
        weights[row[0]] = weights.get(row[0], 0.0) + 1.0

    for row in db.execute(
        text("SELECT book_id FROM favorites WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchall():
        weights[row[0]] = weights.get(row[0], 0.0) + 2.0

    # Incluir ratings como señal explícita (solo positivas ≥ 3★)
    RATING_WEIGHT = {5: 3.0, 4: 2.0, 3: 1.0}
    for row in db.execute(
        text("SELECT book_id, rating FROM ratings WHERE user_id = :uid AND rating >= 3"),
        {"uid": user_id},
    ).fetchall():
        w = RATING_WEIGHT.get(int(row[1]), 0.0)
        weights[row[0]] = weights.get(row[0], 0.0) + w

    return weights


def _get_all_books(db: Session, max_books: int = 5000) -> pd.DataFrame:
    """
    Recupera libros con los campos del dataset.

    Para evitar cargar 32k embeddings en RAM en cada request, limita a los
    `max_books` libros que ya tengan embeddings calculados (los más valorados),
    o los más valorados si no hay embeddings aún.
    """
    rows = db.execute(
        text(
            "SELECT id, title, author, genre, format, cover_url, "
            "price, currency, average_rating FROM books "
            "WHERE embedding IS NOT NULL "
            "ORDER BY average_rating DESC NULLS LAST "
            "LIMIT :lim"
        ),
        {"lim": max_books},
    ).fetchall()

    # Si no hay embeddings aún (primer arranque), usar los mejor valorados
    if not rows:
        rows = db.execute(
            text(
                "SELECT id, title, author, genre, format, cover_url, "
                "price, currency, average_rating FROM books "
                "ORDER BY average_rating DESC NULLS LAST "
                "LIMIT :lim"
            ),
            {"lim": max_books},
        ).fetchall()

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(
        rows,
        columns=["id", "title", "author", "genre", "format",
                 "cover_url", "price", "currency", "average_rating"],
    )


def _get_popular_books(db: Session, limit: int) -> pd.DataFrame:
    """Recupera libros ordenados por popularidad (nº de likes + favoritos)."""
    rows = db.execute(
        text("""
            SELECT b.id, b.title, b.author, b.genre,
                   COALESCE(COUNT(DISTINCT l.id), 0) + COALESCE(COUNT(DISTINCT f.id), 0) AS popularity
            FROM books b
            LEFT JOIN likes l ON l.book_id = b.id
            LEFT JOIN favorites f ON f.book_id = b.id
            GROUP BY b.id, b.title, b.author, b.genre
            ORDER BY popularity DESC, b.id
            LIMIT :lim
        """),
        {"lim": limit},
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=["id", "title", "author", "genre", "popularity"])


# ---------------------------------------------------------------------------
# Gestión de embeddings con caché en PostgreSQL
# ---------------------------------------------------------------------------

def _get_embeddings(db: Session, all_books: pd.DataFrame) -> np.ndarray:
    """
    Obtiene embeddings semánticos para todos los libros del DataFrame.

    Primero intenta recuperarlos de la columna `embedding` en la BD.
    Calcula y persiste los que falten usando all-MiniLM-L6-v2.
    Devuelve una matriz (n_books, 384) en el mismo orden que all_books.
    """
    model = _get_model()
    book_ids = all_books["id"].tolist()

    # Recuperar embeddings ya cacheados
    rows = db.execute(
        text(
            "SELECT id, embedding FROM books "
            "WHERE id = ANY(:ids) AND embedding IS NOT NULL"
        ),
        {"ids": book_ids},
    ).fetchall()

    cached: Dict[int, np.ndarray] = {}
    for row in rows:
        if row[1] is not None:
            cached[int(row[0])] = np.array(row[1], dtype=np.float32)

    # Calcular los que faltan — en batches para no saturar RAM con 32k libros
    EMBED_BATCH = 512
    missing_books = all_books[~all_books["id"].isin(cached.keys())]
    if not missing_books.empty:
        logger.info("Calculando embeddings para %d libros...", len(missing_books))
        missing_list = missing_books.reset_index(drop=True)

        for batch_start in range(0, len(missing_list), EMBED_BATCH):
            batch = missing_list.iloc[batch_start: batch_start + EMBED_BATCH]
            t = batch["title"].fillna("")
            texts = (
                t + " " + t + " " +
                batch["author"].fillna("") + " " +
                batch["genre"].fillna("") + " " +
                batch["format"].fillna("")
            ).tolist()

            batch_embs = model.encode(
                texts, convert_to_numpy=True, show_progress_bar=False, batch_size=64
            ).astype(np.float32)

            update_rows = []
            for i, (_, row) in enumerate(batch.iterrows()):
                bid = int(row["id"])
                cached[bid] = batch_embs[i]
                update_rows.append({"emb": batch_embs[i].tolist(), "id": bid})

            try:
                for r in update_rows:
                    db.execute(
                        text("UPDATE books SET embedding = :emb WHERE id = :id"), r
                    )
                db.commit()
                logger.info(
                    "  Embeddings: %d / %d",
                    min(batch_start + EMBED_BATCH, len(missing_list)),
                    len(missing_list),
                )
            except Exception as exc:
                logger.error("Error persistiendo batch de embeddings: %s", exc)
                db.rollback()

    # Devolver matriz en el orden original de all_books
    return np.vstack([cached[int(bid)] for bid in book_ids])


# ---------------------------------------------------------------------------
# Algoritmo 1: Filtrado basado en contenido (embeddings semánticos)
# ---------------------------------------------------------------------------

def content_based_recommendations(
    db: Session, user_id: int, limit: int = 10
) -> List[Dict]:
    """
    Genera recomendaciones usando embeddings semánticos (all-MiniLM-L6-v2).

    Perfil del usuario = media ponderada de sus libros interactuados:
      - favorito × 2
      - like    × 1
    """
    weights = _get_user_interactions(db, user_id)
    all_books = _get_all_books(db)
    if all_books.empty:
        return []

    # Cold start: sin interacciones → libros mejor valorados del dataset
    if not weights:
        source = all_books.sort_values("average_rating", ascending=False).head(limit)
        return [
            {
                "book_id": int(row["id"]),
                "title": row["title"],
                "author": row["author"],
                "genre": row["genre"],
                "score": round(float(row["average_rating"]) / 5.0, 4)
                if row["average_rating"] else 0.5,
                "reason": "Mejor valorado por la comunidad",
            }
            for _, row in source.iterrows()
        ]

    # Obtener embeddings (con caché en PostgreSQL)
    try:
        emb_matrix = _get_embeddings(db, all_books)
    except Exception as exc:
        logger.error("Error obteniendo embeddings: %s", exc)
        return []

    interacted = list(weights.keys())
    interacted_idx = all_books.index[all_books["id"].isin(interacted)].tolist()
    if not interacted_idx:
        return []

    # Perfil = media ponderada de los vectores del usuario
    user_vector = np.zeros(emb_matrix.shape[1], dtype=np.float32)
    total_weight = 0.0
    for idx in interacted_idx:
        bid = int(all_books.iloc[idx]["id"])
        w = weights.get(bid, 1.0)
        user_vector += emb_matrix[idx] * w
        total_weight += w

    user_profile = (user_vector / total_weight).reshape(1, -1)
    scores = cosine_similarity(user_profile, emb_matrix).flatten()

    all_books = all_books.copy()
    all_books["score"] = scores

    candidates = (
        all_books[~all_books["id"].isin(interacted)]
        .sort_values("score", ascending=False)
        .head(limit)
    )

    result = []
    for _, row in candidates.iterrows():
        genre_label = row["genre"] if row["genre"] else "libros que te gustan"
        result.append(
            {
                "book_id": int(row["id"]),
                "title": row["title"],
                "author": row["author"],
                "genre": row["genre"],
                "score": round(float(row["score"]), 4),
                "reason": f"Similar a tus favoritos de {genre_label}",
            }
        )
    return result


# ---------------------------------------------------------------------------
# Algoritmo 2: Filtrado colaborativo Item-Item
# ---------------------------------------------------------------------------

def collaborative_filtering(
    db: Session, user_id: int, limit: int = 10
) -> List[Dict]:
    """
    Filtrado colaborativo Item-Item.

    Más robusto que User-User ante matrices dispersas.
    Puntúa candidatos como suma ponderada de similitudes con los libros
    con los que ya interactuó el usuario (incluye likes, favoritos y ratings).
    """
    rows = db.execute(
        text(
            "SELECT user_id, book_id, 1.0 AS w FROM likes "
            "UNION ALL "
            "SELECT user_id, book_id, 2.0 AS w FROM favorites "
            "UNION ALL "
            "SELECT user_id, book_id, "
            "  CASE rating WHEN 5 THEN 3.0 WHEN 4 THEN 2.0 WHEN 3 THEN 1.0 ELSE 0.0 END "
            "FROM ratings WHERE rating >= 3"
        )
    ).fetchall()

    if not rows:
        return []

    df = pd.DataFrame(rows, columns=["user_id", "book_id", "w"])
    # Sumar pesos de todas las fuentes para el mismo par usuario-libro
    df = df.groupby(["user_id", "book_id"], as_index=False)["w"].sum()

    if user_id not in df["user_id"].values:
        return []

    matrix = df.pivot_table(
        index="user_id", columns="book_id", values="w", fill_value=0.0
    )

    if user_id not in matrix.index:
        return []

    # Similitud Item-Item (sobre la matriz transpuesta)
    item_sim = cosine_similarity(matrix.T)
    item_sim_df = pd.DataFrame(item_sim, index=matrix.columns, columns=matrix.columns)

    user_row = matrix.loc[user_id]
    user_books = set(user_row[user_row > 0].index.tolist())

    # Puntuar candidatos: suma ponderada de similitudes con libros del usuario
    candidate_scores: Dict[int, float] = {}
    for book_id in user_books:
        if book_id not in item_sim_df.index:
            continue
        w = float(user_row[book_id])
        for candidate_id, sim in item_sim_df[book_id].items():
            if candidate_id in user_books:
                continue
            candidate_scores[candidate_id] = (
                candidate_scores.get(candidate_id, 0.0) + sim * w
            )

    if not candidate_scores:
        return []

    top_ids = sorted(
        candidate_scores, key=candidate_scores.__getitem__, reverse=True
    )[:limit]
    max_score = max(candidate_scores[bid] for bid in top_ids)

    book_rows = db.execute(
        text("SELECT id, title, author, genre FROM books WHERE id = ANY(:ids)"),
        {"ids": top_ids},
    ).fetchall()

    result = []
    for row in book_rows:
        score = (
            round(candidate_scores.get(row[0], 0.0) / max_score, 4)
            if max_score > 0
            else 0.0
        )
        result.append(
            {
                "book_id": row[0],
                "title": row[1],
                "author": row[2],
                "genre": row[3],
                "score": score,
                "reason": "Lectores con gustos similares también disfrutaron este libro",
            }
        )

    return sorted(result, key=lambda x: x["score"], reverse=True)


# ---------------------------------------------------------------------------
# Recomendador híbrido principal
# ---------------------------------------------------------------------------

def get_recommendations(db: Session, user_id: int, limit: int = 10) -> Dict:
    """
    Sistema híbrido de recomendación.

    Estrategia según número de interacciones únicas del usuario:
      - 0        → libros populares (cold start)
      - 1-9      → solo filtrado por contenido semántico
      - 10+      → híbrido (Item-Item CF 50 % + contenido semántico 50 %)
    """
    weights = _get_user_interactions(db, user_id)
    total_interactions = len(weights)

    if total_interactions == 0:
        recs = content_based_recommendations(db, user_id, limit)
        algorithm = "popular"

    elif total_interactions < 10:
        recs = content_based_recommendations(db, user_id, limit)
        algorithm = "content-based"

    else:
        cb_recs = content_based_recommendations(db, user_id, limit)
        cf_recs = collaborative_filtering(db, user_id, limit)

        if cf_recs:
            seen: set = set()
            merged: List[Dict] = []

            # 50 % Item-Item CF
            for rec in cf_recs[: limit // 2]:
                if rec["book_id"] not in seen:
                    seen.add(rec["book_id"])
                    merged.append(rec)

            # Rellenar con contenido semántico
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
        "user_id": user_id,
        "recommendations": recs[:limit],
        "algorithm": algorithm,
        "total": len(recs[:limit]),
    }


# ---------------------------------------------------------------------------
# Libros similares (sin contexto de usuario)
# ---------------------------------------------------------------------------

def get_similar_books(db: Session, book_id: int, limit: int = 5) -> List[Dict]:
    """Devuelve libros similares usando similitud de embeddings semánticos."""
    all_books = _get_all_books(db)
    if all_books.empty or book_id not in all_books["id"].values:
        return []

    try:
        emb_matrix = _get_embeddings(db, all_books)
    except Exception as exc:
        logger.error("Error obteniendo embeddings para libros similares: %s", exc)
        return []

    idx = int(all_books.index[all_books["id"] == book_id][0])
    scores = cosine_similarity(emb_matrix[idx].reshape(1, -1), emb_matrix).flatten()

    all_books = all_books.copy()
    all_books["score"] = scores

    similar = (
        all_books[all_books["id"] != book_id]
        .sort_values("score", ascending=False)
        .head(limit)
    )

    return [
        {
            "book_id": int(row["id"]),
            "title": row["title"],
            "author": row["author"],
            "genre": row["genre"],
            "score": round(float(row["score"]), 4),
        }
        for _, row in similar.iterrows()
    ]
