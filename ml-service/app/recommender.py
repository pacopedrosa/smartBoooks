import logging
from typing import List, Dict, Tuple, Optional

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
    """Recupera todos los libros de la base de datos."""
    rows = db.execute(
        text("SELECT id, title, author, genre, description FROM books ORDER BY id")
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=["id", "title", "author", "genre", "description"])


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

    # Calcular los que faltan
    missing_books = all_books[~all_books["id"].isin(cached.keys())]
    if not missing_books.empty:
        texts = (
            missing_books["title"].fillna("") + " " +
            missing_books["author"].fillna("") + " " +
            missing_books["genre"].fillna("") + " " +
            missing_books["description"].fillna("")
        ).tolist()

        new_embs = model.encode(
            texts, convert_to_numpy=True, show_progress_bar=False
        ).astype(np.float32)

        for i, (_, row) in enumerate(missing_books.iterrows()):
            bid = int(row["id"])
            cached[bid] = new_embs[i]
            try:
                db.execute(
                    text("UPDATE books SET embedding = :emb WHERE id = :id"),
                    {"emb": new_embs[i].tolist(), "id": bid},
                )
            except Exception as exc:
                logger.warning(
                    "No se pudo guardar embedding para libro %d: %s", bid, exc
                )

        try:
            db.commit()
        except Exception as exc:
            logger.error("Error al persistir embeddings: %s", exc)
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
    liked, favorited = _get_user_interactions(db, user_id)
    all_books = _get_all_books(db)
    if all_books.empty:
        return []

    # Cold start: sin interacciones → libros más populares
    if not liked and not favorited:
        popular = _get_popular_books(db, limit)
        source = popular if not popular.empty else all_books.head(limit)
        return [
            {
                "book_id": int(row["id"]),
                "title": row["title"],
                "author": row["author"],
                "genre": row["genre"],
                "score": round(0.5, 4),
                "reason": "Libro popular entre nuestros lectores",
            }
            for _, row in source.iterrows()
        ]

    # Obtener embeddings (con caché en PostgreSQL)
    try:
        emb_matrix = _get_embeddings(db, all_books)
    except Exception as exc:
        logger.error("Error obteniendo embeddings: %s", exc)
        return []

    # Pesos ponderados: favorito = 2, like = 1
    weights: Dict[int, float] = {}
    for bid in liked:
        weights[bid] = weights.get(bid, 0.0) + 1.0
    for bid in favorited:
        weights[bid] = weights.get(bid, 0.0) + 2.0

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
                "reason": f"Similar a tus libros favoritos de {genre_label}",
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
    con los que ya interactuó el usuario (favorito = 2, like = 1).
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
    # Combinar pesos si el mismo usuario tiene like Y favorito del mismo libro
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
    liked, favorited = _get_user_interactions(db, user_id)
    total_interactions = len(set(liked + favorited))

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
    """Recupera todos los libros de la base de datos."""
    rows = db.execute(
        text("SELECT id, title, author, genre, description FROM books ORDER BY id")
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=["id", "title", "author", "genre", "description"])


# ---------------------------------------------------------------------------
# Algoritmo 1: Filtrado basado en contenido (TF-IDF)
# ---------------------------------------------------------------------------

def content_based_recommendations(
    db: Session, user_id: int, limit: int = 10
) -> List[Dict]:
    """
    Genera recomendaciones usando similitud de contenido TF-IDF.

    El perfil del usuario se construye como la media vectorial de los libros
    con los que ha interactuado (likes + favoritos). A continuación se
    calcula la similitud coseno con el resto del catálogo.
    """
    liked, favorited = _get_user_interactions(db, user_id)
    interacted = list(set(liked + favorited))

    all_books = _get_all_books(db)
    if all_books.empty:
        return []

    # Texto de características: título + autor + género + descripción
    all_books["features"] = (
        all_books["title"].fillna("") + " "
        + all_books["author"].fillna("") + " "
        + all_books["genre"].fillna("") + " "
        + all_books["description"].fillna("")
    )

    # === Cold start: sin interacciones → libros ordenados por id (variedad) ===
    if not interacted:
        sample = all_books.head(limit)
        return [
            {
                "book_id": int(row["id"]),
                "title": row["title"],
                "author": row["author"],
                "genre": row["genre"],
                "score": round(0.5, 4),
                "reason": "Recomendado para nuevos usuarios",
            }
            for _, row in sample.iterrows()
        ]

    # TF-IDF sobre todo el catálogo
    tfidf = TfidfVectorizer(max_features=5000, sublinear_tf=True)
    try:
        tfidf_matrix = tfidf.fit_transform(all_books["features"])
    except Exception as exc:
        logger.error("TF-IDF error: %s", exc)
        return []

    interacted_idx = all_books.index[all_books["id"].isin(interacted)].tolist()
    if not interacted_idx:
        return []

    # Perfil de usuario = media de los vectores de sus libros
    user_profile = np.mean(
        tfidf_matrix[interacted_idx].toarray(), axis=0
    ).reshape(1, -1)

    scores = cosine_similarity(user_profile, tfidf_matrix).flatten()
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
                "reason": f"Similar a tus libros favoritos de {genre_label}",
            }
        )
    return result


# ---------------------------------------------------------------------------
# Algoritmo 2: Filtrado colaborativo (User-User)
# ---------------------------------------------------------------------------

def collaborative_filtering(
    db: Session, user_id: int, limit: int = 10
) -> List[Dict]:
    """
    Filtrado colaborativo basado en usuarios similares.

    Construye una matriz usuario-ítem con las interacciones (likes = 1,
    favoritos = 2) y calcula la similitud coseno entre usuarios.
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

    book_rows = db.execute(
        text("SELECT id, title, author, genre FROM books WHERE id = ANY(:ids)"),
        {"ids": top_book_ids},
    ).fetchall()

    max_count = float(candidate_books.max())
    result = []
    for row in book_rows:
        score = round(float(candidate_books.get(row[0], 1)) / max_count, 4)
        result.append(
            {
                "book_id": row[0],
                "title": row[1],
                "author": row[2],
                "genre": row[3],
                "score": score,
                "reason": "Usuarios con gustos similares también leyeron este libro",
            }
        )

    return sorted(result, key=lambda x: x["score"], reverse=True)


# ---------------------------------------------------------------------------
# Recomendador híbrido principal
# ---------------------------------------------------------------------------

def get_recommendations(db: Session, user_id: int, limit: int = 10) -> Dict:
    """
    Sistema híbrido de recomendación.

    Estrategia según número de interacciones del usuario:
      - 0 interacciones  → libros populares (cold start)
      - 1-4              → solo filtrado por contenido
      - 5+               → híbrido (colaborativo + contenido)
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

            # 50 % colaborativo
            for rec in cf_recs[: limit // 2]:
                if rec["book_id"] not in seen:
                    seen.add(rec["book_id"])
                    merged.append(rec)

            # Rellena con contenido
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
    """Devuelve libros similares al indicado usando similitud TF-IDF."""
    all_books = _get_all_books(db)
    if all_books.empty or book_id not in all_books["id"].values:
        return []

    all_books["features"] = (
        all_books["title"].fillna("") + " "
        + all_books["author"].fillna("") + " "
        + all_books["genre"].fillna("") + " "
        + all_books["description"].fillna("")
    )

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
            "book_id": int(row["id"]),
            "title": row["title"],
            "author": row["author"],
            "genre": row["genre"],
            "score": round(float(row["score"]), 4),
        }
        for _, row in similar.iterrows()
    ]
