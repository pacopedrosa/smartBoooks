import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import get_db
from .schemas import RecommendationResponse, SimilarBooksResponse
from .recommender import get_recommendations, get_similar_books
from .seed import seed_books

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ejecuta el seed del dataset al arrancar el servicio."""
    try:
        seed_books()
    except Exception as exc:
        logger.warning("Seed no completado (no crítico): %s", exc)
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
