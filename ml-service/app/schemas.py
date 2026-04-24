from pydantic import BaseModel
from typing import List, Optional


class BookRecommendation(BaseModel):
    book_id:   int
    title:     str
    author:    str
    genre:     Optional[str]  = None
    cover_url: Optional[str]  = None
    price:     Optional[float] = None
    currency:  Optional[str]  = None
    score:     float
    reason:    str


class RecommendationResponse(BaseModel):
    user_id:         int
    recommendations: List[BookRecommendation]
    algorithm:       str
    total:           int


class SimilarBook(BaseModel):
    book_id:   int
    title:     str
    author:    str
    genre:     Optional[str] = None
    cover_url: Optional[str] = None
    score:     float


class SimilarBooksResponse(BaseModel):
    book_id:      int
    similar_books: List[SimilarBook]


class MetricsResponse(BaseModel):
    k:               int
    sample_size:     int
    hit_rate:        float
    precision_at_k:  float
    recall_at_k:     float
    ndcg_at_k:       float
    message:         str
