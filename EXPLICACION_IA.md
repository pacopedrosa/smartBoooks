# SmartBooks — Explicación completa del sistema de IA

---

## 1. ¿Es válido como proyecto de IA y Big Data?

**Sí, es completamente válido.** El proyecto implementa un sistema de recomendación híbrido con varias capas de inteligencia artificial. Aquí la tabla resumen:

| Categoría | Técnica usada | Tipo de aprendizaje |
|-----------|--------------|---------------------|
| Deep Learning | `all-MiniLM-L6-v2` (modelo Transformer/SBERT) | No supervisado (preentrenado) |
| Recomendación | Filtrado basado en contenido semántico | No supervisado |
| Recomendación | Filtrado colaborativo Item-Item | No supervisado |
| Big Data | 32k libros + embeddings de 384 dimensiones cacheados en PostgreSQL, procesados en batches de 512 | ✓ |

### ¿Es válido usar un modelo preentrenado?

Depende de **cómo** se use:

- **Usar un LLM para que "haga todo"** (tipo ChatGPT que genera recomendaciones con un prompt) → **No sería válido**, porque no hay sistema propio, solo se llama a una API externa.
- **Usar un modelo preentrenado como herramienta dentro de tu propio sistema** → **Sí es válido**, y es exactamente lo que hace este proyecto.

En SmartBooks, `all-MiniLM-L6-v2` solo hace una tarea pequeña: convertir texto en números (embeddings). **Todo lo demás es el sistema propio**: el sistema de pesos por interacción, el perfil del usuario, el filtrado colaborativo Item-Item, la lógica híbrida, el cold start... Eso es la IA del proyecto.

> Es como usar una calculadora en un examen de ingeniería: la calculadora no resuelve el problema, tú sí.

---

## 2. ¿Qué es el modelo all-MiniLM-L6-v2 y cómo sabe que dos libros son parecidos?

### ¿Cómo aprendió?

El modelo fue entrenado leyendo **millones de textos de internet** (Wikipedia, libros, foros, reseñas...). Durante ese entrenamiento aprendió que ciertas palabras y frases aparecen juntas en los mismos contextos.

Aprendió que "Tolkien", "elfos", "magia", "aventura épica", "Tierra Media" siempre aparecen en los mismos párrafos y conversaciones. Así que cuando le das el texto de dos libros, los convierte en números muy similares porque comparten ese "vocabulario de contexto".

**No lo programó nadie explícitamente.** Lo aprendió solo leyendo texto, igual que un niño aprende que "perro" y "can" significan lo mismo sin que nadie se lo explique directamente.

### ¿Qué hace exactamente?

Su única función en este proyecto es convertir el texto de cada libro en **384 números** (un embedding). Esos números se guardan en la columna `embedding` de la base de datos PostgreSQL.

```
El Hobbit          → [0.23, -0.11, 0.87, 0.04, -0.52, ... ] (384 números)
El Señor de Anillos→ [0.21, -0.09, 0.85, 0.06, -0.49, ... ] (384 números)
50 Sombras de Grey → [-0.67, 0.43, -0.12, 0.88, 0.31, ... ] (384 números)
```

Los dos primeros tienen números muy parecidos → son libros **similares**.
El tercero tiene números muy distintos → es un libro **diferente**.

### ¿Qué es el "mapa" del que se habla?

No existe físicamente. Es una metáfora para explicar algo matemático. Imagina que esos 384 números colocan cada libro en un punto de un espacio enorme. Los libros parecidos quedan cerca, los distintos quedan lejos. La "distancia" entre puntos se mide con la **similitud coseno** (explicada más adelante).

---

## 3. Los cuatro algoritmos del sistema

### Resumen visual

```
¿Cuántas interacciones tiene el usuario?

0 ──────────► Popularidad (cold start, sin IA)
1 a 9 ──────► Mapa semántico (IA de contenido) + boost por autor
10+ ────────► Mapa semántico (50%) + Comportamiento de otros usuarios (50%) + boost por autor
```

---

### Algoritmo 1 — Cold Start (0 interacciones)

El sistema no sabe nada del usuario. Solución: **¿qué le gusta a todo el mundo?**

Devuelve los libros con mejor nota media del dataset. Como cuando llegas a Netflix sin haber visto nada y te muestra "Los más populares". No hay IA aquí, es popularidad pura.

**Código relevante en `recommender.py`:**
```python
source = all_books.sort_values("average_rating", ascending=False).head(limit)
```

---

### Algoritmo 2 — Basado en contenido semántico (1-9 interacciones)

**Analogía:** El sistema tiene un post-it con tus gustos y busca libros parecidos.

**Pasos:**
1. Mira los libros con los que interactuaste (likes, favoritos, ratings)
2. Localiza esos libros en el espacio de 384 dimensiones
3. Calcula el **punto medio** de todos ellos — ese es tu "perfil"
4. Busca qué otros libros están más cerca de ese punto medio
5. Te los recomienda

> Si te gustaron 3 libros de fantasía épica, tu punto medio estará en la zona "fantasía épica" y el sistema te recomendará más de esa zona.

**Pesos de las interacciones:**

| Interacción | Peso |
|-------------|------|
| Rating 5★ | 3.0 |
| Favorito | 2.0 |
| Rating 4★ | 2.0 |
| Like | 1.0 |
| Rating 3★ | 1.0 |
| Rating 1-2★ | 0 (ignorado) |

Los pesos hacen que tu perfil se acerque más a lo que más te gustó: si guardaste algo en favoritos es porque te encantó, y eso debe pesar más que un simple like.

**Código relevante en `recommender.py`:**
```python
# Perfil = media ponderada de los vectores del usuario
user_vector += emb_matrix[idx] * w
user_profile = (user_vector / total_weight).reshape(1, -1)
scores = cosine_similarity(user_profile, emb_matrix).flatten()
```

---

### Algoritmo 3 — Filtrado colaborativo Item-Item (10+ interacciones)

**Analogía:** Amazon y el "los que compraron X también compraron Y".

No mira el contenido del libro. Mira el **comportamiento de todos los usuarios**:

1. Construye una tabla: filas = usuarios, columnas = libros, celdas = cuánto le gustó
2. Compara libros entre sí: "¿los usuarios que leyeron el libro A también leyeron el libro B?"
3. Si muchos usuarios que marcaron A también marcaron B → A y B son "similares según comportamiento"
4. Si a ti te gustó A, te recomienda B

> No sabe nada del contenido de los libros. Solo sabe que la gente que los lee suele coincidir.

**Código relevante en `recommender.py`:**
```python
# Similitud entre libros basada en comportamiento de usuarios
item_sim = cosine_similarity(matrix.T)
```

---

### Algoritmo 4 — Híbrido (10+ interacciones)

Mezcla los dos algoritmos anteriores para cubrir sus debilidades:

**Analogía:** Buscas restaurante y consultas dos fuentes:
- **El crítico gastronómico** (= contenido semántico): analiza el menú y los ingredientes. Si te gustó la paella, te recomienda otros arroces mediterráneos porque el *contenido* es similar.
- **TripAdvisor** (= colaborativo): no sabe nada de cocina, solo sabe que "la gente que fue al restaurante X también fue al Y y le encantó".

El híbrido hace: *"toma 5 restaurantes del crítico y 5 de TripAdvisor y dáselos al usuario"*.

Si el crítico falla (un libro nuevo sin mucha descripción), TripAdvisor lo cubre, y viceversa.

**Código relevante en `recommender.py`:**
```python
# 50% del colaborativo (Item-Item)
for rec in cf_recs[:limit // 2]:
    merged.append(rec)

# 50% del semántico (rellena hasta llegar al límite)
for rec in cb_recs:
    if rec["book_id"] not in seen and len(merged) < limit:
        merged.append(rec)
```

---

## 4. ¿Qué es la similitud coseno y dónde se calcula?

La similitud coseno es la fórmula que mide qué tan parecidos son dos conjuntos de 384 números. Devuelve un valor entre 0 y 1: cuanto más cercano a 1, más parecidos son.

Se calcula en tres puntos del archivo `recommender.py`:

| Dónde | Para qué | Código |
|-------|----------|--------|
| Función `content_based_recommendations` | Compara el perfil del usuario contra todos los libros | `scores = cosine_similarity(user_profile, emb_matrix).flatten()` |
| Función `collaborative_filtering` | Compara libros entre sí según comportamiento de usuarios | `item_sim = cosine_similarity(matrix.T)` |
| Función `get_similar_books` | Compara un libro concreto contra todos los demás | `scores = cosine_similarity(emb_matrix[idx].reshape(1, -1), emb_matrix).flatten()` |

---

## 5. Métricas de evaluación implementadas

El sistema incluye un endpoint `/metrics` que evalúa automáticamente la calidad de las recomendaciones usando la técnica **Leave-One-Out** sobre una muestra de usuarios reales.

### ¿Cómo funciona Leave-One-Out?

1. Se toman usuarios que tengan al menos 2 interacciones registradas
2. Para cada uno, se **oculta la interacción más reciente** (ese libro es el **ground truth** — la "respuesta correcta" que el sistema debe adivinar)
3. Se generan recomendaciones con el historial restante
4. Se mide si el libro ocultado aparece entre los top-K recomendados
5. Se repite para todos los usuarios de la muestra y se hace la media

**¿Por qué se llama "ground truth"?**

Ground truth significa "la verdad real que queremos predecir". En este contexto, es el libro que el usuario interactuó más recientemente — algo que realmente le interesó. Si el sistema lo recomienda sin haberlo "visto", significa que ha entendido bien el perfil del usuario.

```
Usuario: [Fantasy1, Fantasy2, Fantasy3, ..., Fantasy10]  ← historial completo
                                               ↑
                                       ground truth (se oculta)

Sistema recibe: [Fantasy1, Fantasy2, Fantasy3, ...]   ← historial reducido
Sistema genera: Top-10 recomendaciones
¿Aparece Fantasy10 en el top-10? → acierto ✓ / fallo ✗
```

La evaluación es **estratificada por género**: los candidatos se filtran al mismo género que el ground truth (~380 libros), y se limita a máximo 3 libros por autor para evitar que ediciones múltiples del mismo título dominen el ranking artificialmente.

### Las 4 métricas calculadas

#### Hit Rate@K — "¿Le acerté al menos una vez?"
De todos los usuarios evaluados, ¿a qué porcentaje le apareció el libro ocultado entre las top-K recomendaciones?

> 100 usuarios evaluados → a 72 les apareció el libro correcto entre los top-10 → **Hit Rate = 0.72 (72%)**

Un valor alto significa que el sistema acierta con frecuencia.

#### Precision@K — "¿Cuántas de las recomendaciones fueron buenas?"
De los K libros recomendados, ¿cuántos eran relevantes? Se calcula por usuario y se hace la media.

> Se recomiendan 10 libros y 1 era el correcto → Precision = 1/10 = **0.10**

En Leave-One-Out solo hay 1 item correcto por usuario, así que el valor máximo posible es `1/K`.

#### Recall@K — "¿Encontré lo que buscaba?"
De todos los libros relevantes para el usuario, ¿cuántos aparecieron en las recomendaciones? En Leave-One-Out solo hay 1 libro relevante, así que equivale al Hit Rate individual.

> Si el libro correcto aparece → Recall = 1.0. Si no aparece → Recall = 0.0. La media sobre todos los usuarios da el resultado final.

#### NDCG@K — "¿Pusiste los mejores primero?"
Igual que las anteriores pero penaliza que el libro correcto aparezca tarde en la lista. Un acierto en el puesto 1 vale más que uno en el puesto 10.

> Acierto en posición 1 → NDCG = 1.0 (máximo)
> Acierto en posición 5 → NDCG ≈ 0.43
> Acierto en posición 10 → NDCG ≈ 0.29
> Sin acierto → NDCG = 0.0

### Cómo usar el endpoint

```
GET /metrics?k=10&sample_size=50
```

| Parámetro | Descripción | Por defecto |
|-----------|-------------|-------------|
| `k` | Cuántas recomendaciones evaluar (top-K) | 10 |
| `sample_size` | Cuántos usuarios incluir en la muestra | 50 |

**Respuesta real del sistema (resultado obtenido en pruebas):**
```json
{
  "k": 10,
  "sample_size": 50,
  "hit_rate": 0.68,
  "precision_at_k": 0.068,
  "recall_at_k": 0.68,
  "ndcg_at_k": 0.6043,
  "message": "Evaluado sobre 50 usuarios con Leave-One-Out (0 excluidos por ground truth fuera del catálogo)"
}
```

### ¿Cómo interpretar los resultados?

El sistema evalúa sobre ~380 candidatos del mismo género. El azar puro acertaría en el 2.6% de los casos (10/380). Los resultados obtenidos son **26x mejores que el azar**.

| Métrica | Resultado real | Azar puro | Ratio vs azar | Interpretación |
|---------|---------------|-----------|---------------|----------------|
| Hit Rate@10 | 68% | 2.6% | ~26x | BUENO |
| NDCG@10 | 60.4% | ~2% | ~30x | BUENO |

Para comparar: Netflix y Spotify reportan 20-40%, pero tienen millones de usuarios con años de historial. Con un dataset de 32k libros, obtener 26x sobre el azar es un resultado sólido, comparable con sistemas de producción reales.

**Umbrales de evaluación:**

| Métrica | Bajo | Aceptable | Bueno |
|---------|------|-----------|-------|
| Hit Rate@10 | < 10% | 10% – 25% | > 25% |
| Precision@10 | < 1.0% | 1.0% – 2.5% | > 2.5% |
| NDCG@10 | < 5% | 5% – 15% | > 15% |

---

## 6. Stack tecnológico del servicio de IA

| Librería | Versión | Para qué se usa |
|----------|---------|-----------------|
| `sentence-transformers` | 3.0.1 | Cargar y usar el modelo all-MiniLM-L6-v2 |
| `scikit-learn` | 1.4.0 | Calcular la similitud coseno |
| `numpy` | 1.26.3 | Operaciones con vectores y matrices |
| `pandas` | 2.1.4 | Manipular los datos de libros e interacciones |
| `fastapi` | 0.109.0 | Exponer los endpoints `/recommendations` y `/similar` |
| `sqlalchemy` | 2.0.25 | Acceder a PostgreSQL (libros, embeddings, interacciones) |
