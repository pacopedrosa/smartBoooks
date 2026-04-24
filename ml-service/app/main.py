import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import get_db, SessionLocal
from .schemas import RecommendationResponse, SimilarBooksResponse, MetricsResponse
from .recommender import get_recommendations, get_similar_books, evaluate_metrics, _get_all_books, _get_embeddings
from .seed import seed_books

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _precompute_embeddings() -> None:
    """Pre-calcula y cachea embeddings de todos los libros en PostgreSQL."""
    db = SessionLocal()
    try:
        all_books = _get_all_books(db)
        if all_books.empty:
            logger.info("Pre-compute embeddings: no hay libros aún.")
            return
        missing_count = db.execute(
            __import__('sqlalchemy').text(
                "SELECT COUNT(*) FROM books WHERE embedding IS NULL"
            )
        ).scalar() or 0
        if missing_count == 0:
            logger.info("Pre-compute embeddings: todos los libros ya tienen embedding cacheado.")
            return
        logger.info(
            "Pre-computando embeddings para %d libros sin caché (esto tarda unos minutos)...",
            missing_count,
        )
        _get_embeddings(db, all_books)
        logger.info("Pre-compute embeddings completado.")
    except Exception as exc:
        logger.error("Error pre-computando embeddings: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ejecuta el seed y pre-computa embeddings al arrancar el servicio."""
    try:
        seed_books()
    except Exception as exc:
        logger.warning("Seed no completado (no crítico): %s", exc)
    # Pre-cómputo en background para no bloquear el arranque del servidor
    asyncio.get_event_loop().run_in_executor(None, _precompute_embeddings)
    yield


app = FastAPI(
    title="SmartBooks ML Service",
    description="Servicio de recomendación de libros mediante Inteligencia Artificial",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ml-service"}


@app.get("/recommendations/{user_id}", response_model=RecommendationResponse)
def recommendations_endpoint(
    user_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Genera recomendaciones personalizadas para un usuario."""
    try:
        result = get_recommendations(db, user_id, limit)
        return result
    except Exception as exc:
        logger.error("Error generating recommendations for user %d: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="Error al generar recomendaciones")


@app.get("/similar/{book_id}", response_model=SimilarBooksResponse)
def similar_books_endpoint(
    book_id: int,
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Devuelve libros similares a uno dado."""
    try:
        similar = get_similar_books(db, book_id, limit)
        if similar is None:
            raise HTTPException(status_code=404, detail="Libro no encontrado")
        return {"book_id": book_id, "similar_books": similar}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error finding similar books for book %d: %s", book_id, exc)
        raise HTTPException(status_code=500, detail="Error al buscar libros similares")


@app.get("/metrics", response_model=MetricsResponse)
def metrics_endpoint(
    k: int = Query(default=10, ge=1, le=50),
    sample_size: int = Query(default=50, ge=5, le=200),
    db: Session = Depends(get_db),
):
    """
    Evalúa la calidad del sistema de recomendación usando Leave-One-Out.

    Para cada usuario de la muestra, oculta su interacción más reciente,
    genera recomendaciones y mide si el libro ocultado aparece en top-K.

    Métricas devueltas:
    - hit_rate       : % de usuarios donde se acertó al menos 1 libro
    - precision_at_k : media de aciertos / K por usuario
    - recall_at_k    : media de aciertos / total relevantes por usuario
    - ndcg_at_k      : calidad del orden (penaliza aciertos tardíos en la lista)
    """
    try:
        result = evaluate_metrics(db, k=k, sample_size=sample_size)
        return result
    except Exception as exc:
        logger.error("Error evaluando métricas: %s", exc)
        raise HTTPException(status_code=500, detail="Error al calcular métricas")
