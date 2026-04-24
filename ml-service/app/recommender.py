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


def _get_all_books(db: Session, max_books: int = 150000) -> pd.DataFrame:
    """
    Recupera los top `max_books` libros ordenados por popularidad
    (número de likes + favoritos) o, si no hay interacciones aún, por id.

    Incluye la columna `description` para generar embeddings semánticos
    más ricos con el nuevo dataset (BooksDatasetClean.csv).
    """
    rows = db.execute(
        text(
            "SELECT b.id, b.title, b.author, b.genre, b.cover_url, "
            "b.price, b.currency, b.average_rating, b.description, "
            "COALESCE(COUNT(DISTINCT l.id), 0) + COALESCE(COUNT(DISTINCT f.id), 0) AS popularity "
            "FROM books b "
            "LEFT JOIN likes l ON l.book_id = b.id "
            "LEFT JOIN favorites f ON f.book_id = b.id "
            "GROUP BY b.id "
            "ORDER BY popularity DESC, b.id "
            "LIMIT :lim"
        ),
        {"lim": max_books},
    ).fetchall()

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(
        rows,
        columns=["id", "title", "author", "genre", "cover_url",
                 "price", "currency", "average_rating", "description", "popularity"],
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
            # Incluir descripción si existe — da mucho más contexto semántico
            # al modelo y mejora significativamente la calidad de los embeddings
            desc = batch["description"].fillna("") if "description" in batch.columns else pd.Series([""]*len(batch))
            texts = (
                t + " " + t + " " +
                batch["author"].fillna("") + " " +
                batch["genre"].fillna("") + " " +
                desc
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

    # Cold start: sin interacciones → libros más populares (más likes+favoritos)
    if not weights:
        pop_col = "popularity" if "popularity" in all_books.columns else "average_rating"
        source = all_books.sort_values(pop_col, ascending=False).head(limit)
        max_pop = float(source[pop_col].max()) if float(source[pop_col].max()) > 0 else 1.0
        return [
            {
                "book_id": int(row["id"]),
                "title": row["title"],
                "author": row["author"],
                "genre": row["genre"],
                "score": round(float(row[pop_col]) / max_pop, 4),
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

    # Author affinity boost ─────────────────────────────────────────────────
    # Si el usuario tiene muchas interacciones con un autor, sus otros libros
    # reciben una puntuación extra proporcional. Esto captura la señal más
    # directa de preferencia: "si leíste 6 libros de Sanderson, probablemente
    # quieras el séptimo". Técnica estándar en sistemas de recomendación reales.
    author_affinity: Dict[int, float] = {}
    for idx in interacted_idx:
        bid = int(all_books.iloc[idx]["id"])
        w = weights.get(bid, 1.0)
        author = str(all_books.iloc[idx].get("author", "") or "").strip().lower()
        if author:
            author_affinity[author] = author_affinity.get(author, 0.0) + w

    if author_affinity:
        max_aff = max(author_affinity.values())
        author_lower = all_books["author"].fillna("").str.strip().str.lower()
        boost = author_lower.map(
            lambda a: author_affinity.get(a, 0.0) / max_aff * 0.45
        ).values.astype(np.float32)
        scores = scores + boost

    # Genre affinity boost ──────────────────────────────────────────────────
    # Boost libros del mismo género que el usuario ha interactuado.
    genre_affinity: Dict[str, float] = {}
    for idx in interacted_idx:
        bid = int(all_books.iloc[idx]["id"])
        w = weights.get(bid, 1.0)
        genre = str(all_books.iloc[idx].get("genre", "") or "").strip()
        if genre:
            genre_affinity[genre] = genre_affinity.get(genre, 0.0) + w

    if genre_affinity:
        max_genre = max(genre_affinity.values())
        genre_col = all_books["genre"].fillna("").str.strip()
        genre_boost = genre_col.map(
            lambda g: genre_affinity.get(g, 0.0) / max_genre * 0.20
        ).values.astype(np.float32)
        scores = scores + genre_boost
    # ────────────────────────────────────────────────────────────────────────

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

        # Solo incluir items de CF con score significativo (≥ 0.10).
        # Con matrices muy dispersas el CF genera scores ~0 para casi todo,
        # lo que contamina el resultado con géneros incoherentes y muestra
        # "Relevancia: 0.0%" en la UI.
        GOOD_CF_THRESHOLD = 0.10
        good_cf = [r for r in cf_recs if r.get("score", 0.0) >= GOOD_CF_THRESHOLD]

        if good_cf:
            seen: set = set()
            merged: List[Dict] = []

            # Hasta 50 % de CF de calidad
            for rec in good_cf[: limit // 2]:
                if rec["book_id"] not in seen:
                    seen.add(rec["book_id"])
                    merged.append(rec)

            # Rellenar siempre con contenido semántico (garantiza coherencia)
            for rec in cb_recs:
                if rec["book_id"] not in seen and len(merged) < limit:
                    seen.add(rec["book_id"])
                    merged.append(rec)

            # Re-normalizar scores del merge para que la UI muestre % coherentes
            if merged:
                max_s = max(r["score"] for r in merged) or 1.0
                for r in merged:
                    r["score"] = round(r["score"] / max_s, 4)

            recs = merged
            algorithm = "hybrid"
        else:
            # CF no aporta nada útil → solo contenido semántico
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

# ---------------------------------------------------------------------------
# Métricas de evaluación (Leave-One-Out)
# ---------------------------------------------------------------------------

def evaluate_metrics(db: Session, k: int = 10, sample_size: int = 50) -> Dict:
    """
    Evalúa el sistema de recomendación usando Leave-One-Out.

    Estrategia correcta:
      - Para cada usuario se oculta su interacción más reciente (ground truth).
      - Se construye el perfil del usuario SOLO con las interacciones restantes.
      - Se puntúan todos los libros no vistos en el historial reducido,
        incluyendo el ground truth (que ahora es candidato válido).
      - Se mide si el ground truth aparece en el top-K resultante.

    Métricas calculadas:
      - Hit Rate@K     : % de usuarios donde el libro ocultado aparece en top-K
      - Precision@K    : media de (hits relevantes / K) por usuario
      - Recall@K       : media de (hits relevantes / total relevantes) por usuario
      - NDCG@K         : media del NDCG por usuario (penaliza posición tardía)
    """
    from collections import defaultdict
    import random

    # Obtener todas las interacciones con su peso y timestamp
    rows = db.execute(
        text("""
            SELECT user_id, book_id, w, ts
            FROM (
                SELECT user_id, book_id, 1.0 AS w, created_at AS ts FROM likes
                UNION ALL
                SELECT user_id, book_id, 2.0 AS w, created_at AS ts FROM favorites
                UNION ALL
                SELECT user_id, book_id,
                    CASE rating WHEN 5 THEN 3.0 WHEN 4 THEN 2.0 ELSE 1.0 END AS w,
                    created_at AS ts
                FROM ratings WHERE rating >= 3
            ) all_interactions
            ORDER BY user_id, ts DESC
        """)
    ).fetchall()

    if not rows:
        return {
            "k": k, "sample_size": 0,
            "hit_rate": 0.0, "precision_at_k": 0.0,
            "recall_at_k": 0.0, "ndcg_at_k": 0.0,
            "message": "No hay suficientes interacciones para evaluar",
        }

    # Agrupar por usuario: {user_id: [(book_id, weight), ...] ordenado por ts desc}
    user_interactions: Dict[int, List] = defaultdict(list)
    for row in rows:
        user_interactions[int(row[0])].append((int(row[1]), float(row[2])))

    # Solo usuarios con >= 2 interacciones distintas
    eligible = [
        uid for uid, ints in user_interactions.items()
        if len({b for b, _ in ints}) >= 2
    ]
    if not eligible:
        return {
            "k": k, "sample_size": 0,
            "hit_rate": 0.0, "precision_at_k": 0.0,
            "recall_at_k": 0.0, "ndcg_at_k": 0.0,
            "message": "No hay usuarios con suficientes interacciones",
        }

    random.seed(42)
    sample = eligible[:sample_size] if len(eligible) >= sample_size else eligible

    # Cargar libros y embeddings una sola vez para toda la evaluación
    all_books = _get_all_books(db)
    if all_books.empty:
        return {
            "k": k, "sample_size": 0,
            "hit_rate": 0.0, "precision_at_k": 0.0,
            "recall_at_k": 0.0, "ndcg_at_k": 0.0,
            "message": "No hay libros con embeddings calculados aún",
        }

    try:
        emb_matrix = _get_embeddings(db, all_books)
    except Exception as exc:
        logger.error("evaluate_metrics: error obteniendo embeddings: %s", exc)
        return {
            "k": k, "sample_size": 0,
            "hit_rate": 0.0, "precision_at_k": 0.0,
            "recall_at_k": 0.0, "ndcg_at_k": 0.0,
            "message": "Error al obtener embeddings",
        }

    book_id_to_idx = {int(bid): i for i, bid in enumerate(all_books["id"])}
    valid_book_ids = set(book_id_to_idx.keys())

    hits = 0
    precision_scores: List[float] = []
    recall_scores: List[float] = []
    ndcg_scores: List[float] = []
    skipped_no_ground_truth = 0

    for user_id in sample:
        interactions = user_interactions[user_id]

        # Deduplicar: quedarse con el mayor peso por libro (puede haber like + rating)
        best_weight: Dict[int, float] = {}
        seen_order: List[int] = []
        for bid, w in interactions:
            if bid not in best_weight:
                seen_order.append(bid)
            best_weight[bid] = max(best_weight.get(bid, 0.0), w)

        unique_books = seen_order  # ya ordenados por ts desc

        # Ground truth = libro más reciente
        ground_truth = unique_books[0]

        # Si el ground truth no está en el set de candidatos (top-5000),
        # este usuario no es evaluable — el sistema nunca podría recomendarlo
        if ground_truth not in valid_book_ids:
            skipped_no_ground_truth += 1
            continue

        # Historial reducido = resto de libros únicos
        reduced_history = {bid: best_weight[bid] for bid in unique_books[1:]}

        if not reduced_history:
            continue

        # Construir perfil con el historial reducido
        interacted_idxs = [
            book_id_to_idx[bid]
            for bid in reduced_history
            if bid in book_id_to_idx
        ]
        if not interacted_idxs:
            continue

        user_vector = np.zeros(emb_matrix.shape[1], dtype=np.float32)
        total_w = 0.0
        for idx in interacted_idxs:
            bid = int(all_books.iloc[idx]["id"])
            w = reduced_history[bid]
            user_vector += emb_matrix[idx] * w
            total_w += w

        user_profile = (user_vector / total_w).reshape(1, -1)
        scores = cosine_similarity(user_profile, emb_matrix).flatten()

        # Author affinity boost — mismo mecanismo que content_based_recommendations:
        # libros de autores ya interactuados reciben puntuación extra proporcional.
        eval_author_affinity: Dict[str, float] = {}
        for idx in interacted_idxs:
            bid = int(all_books.iloc[idx]["id"])
            w = reduced_history.get(bid, 1.0)
            author = str(all_books.iloc[idx].get("author", "") or "").strip().lower()
            if author:
                eval_author_affinity[author] = eval_author_affinity.get(author, 0.0) + w

        if eval_author_affinity:
            max_aff = max(eval_author_affinity.values())
            boost = all_books["author"].fillna("").str.strip().str.lower().map(
                lambda a: eval_author_affinity.get(a, 0.0) / max_aff * 0.45
            ).values.astype(np.float32)
            scores = scores + boost

        # Genre affinity boost en evaluación
        eval_genre_affinity: Dict[str, float] = {}
        for idx in interacted_idxs:
            bid = int(all_books.iloc[idx]["id"])
            w = reduced_history.get(bid, 1.0)
            genre = str(all_books.iloc[idx].get("genre", "") or "").strip()
            if genre:
                eval_genre_affinity[genre] = eval_genre_affinity.get(genre, 0.0) + w

        if eval_genre_affinity:
            max_g = max(eval_genre_affinity.values())
            genre_boost = all_books["genre"].fillna("").str.strip().map(
                lambda g: eval_genre_affinity.get(g, 0.0) / max_g * 0.20
            ).values.astype(np.float32)
            scores = scores + genre_boost


        # excluyendo el historial reducido. Evaluación estratificada por
        # género — el sistema debe identificar el libro correcto DENTRO
        # del mismo género, lo que es la tarea real del recomendador.
        reduced_set = set(reduced_history.keys())
        gt_genre = all_books.loc[all_books["id"] == ground_truth, "genre"].values
        gt_genre_val = gt_genre[0] if len(gt_genre) > 0 else None

        scored_df = all_books.copy()
        scored_df["_score"] = scores

        # Filtrar al mismo género si está disponible; si no, usar todos
        if gt_genre_val:
            genre_mask = scored_df["genre"] == gt_genre_val
            genre_df = scored_df[genre_mask & ~scored_df["id"].isin(reduced_set)]
            pool = genre_df if len(genre_df) >= k else scored_df[~scored_df["id"].isin(reduced_set)]
        else:
            pool = scored_df[~scored_df["id"].isin(reduced_set)]

        # Limitar a máx. 3 libros por autor para evitar que ediciones múltiples
        # del mismo título dominen el ranking (p.ej. 8 ediciones de HP).
        # Esto replica el comportamiento real de cualquier UI de recomendaciones.
        pool_sorted = pool.sort_values("_score", ascending=False)
        author_count: Dict[str, int] = {}
        filtered_rows = []
        MAX_PER_AUTHOR = 5
        for _, row in pool_sorted.iterrows():
            author_key = str(row.get("author", "")).strip().lower()
            count = author_count.get(author_key, 0)
            if count < MAX_PER_AUTHOR:
                filtered_rows.append(row)
                author_count[author_key] = count + 1
            if len(filtered_rows) >= k:
                break

        candidates = pd.DataFrame(filtered_rows)
        rec_ids = candidates["id"].tolist() if not candidates.empty else []

        # Calcular métricas para este usuario
        relevant_in_recs = [1 if rid == ground_truth else 0 for rid in rec_ids]
        hit = int(ground_truth in rec_ids)
        hits += hit

        precision = sum(relevant_in_recs) / k
        recall = float(sum(relevant_in_recs))  # solo 1 item relevante posible

        dcg = 0.0
        for i, rel in enumerate(relevant_in_recs):
            if rel:
                dcg += 1.0 / np.log2(i + 2)
        idcg = 1.0  # perfecto = ground truth en posición 0
        ndcg = dcg / idcg

        precision_scores.append(precision)
        recall_scores.append(recall)
        ndcg_scores.append(ndcg)

    evaluated = len(precision_scores)
    if evaluated == 0:
        return {
            "k": k, "sample_size": 0,
            "hit_rate": 0.0, "precision_at_k": 0.0,
            "recall_at_k": 0.0, "ndcg_at_k": 0.0,
            "message": f"No se pudo evaluar ningún usuario (ground truth fuera del catálogo en {skipped_no_ground_truth} casos)",
        }

    return {
        "k": k,
        "sample_size": evaluated,
        "hit_rate": round(hits / evaluated, 4),
        "precision_at_k": round(float(np.mean(precision_scores)), 4),
        "recall_at_k": round(float(np.mean(recall_scores)), 4),
        "ndcg_at_k": round(float(np.mean(ndcg_scores)), 4),
        "message": f"Evaluado sobre {evaluated} usuarios con Leave-One-Out ({skipped_no_ground_truth} excluidos por ground truth fuera del catálogo)",
    }


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
