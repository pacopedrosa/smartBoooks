from pydantic import BaseModel
from typing import List, Optional


class BookRecommendation(BaseModel):
    book_id: int
    title: str
    author: str
    genre: Optional[str] = None
    score: float
    reason: str


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: List[BookRecommendation]
    algorithm: str
    total: int


class SimilarBook(BaseModel):
    book_id: int
    title: str
    author: str
    genre: Optional[str] = None
    score: float


class SimilarBooksResponse(BaseModel):
    book_id: int
    similar_books: List[SimilarBook]
