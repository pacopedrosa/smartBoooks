"""
Seed de usuarios ficticios con interacciones variadas para probar el algoritmo hybrid
y verificar que las métricas Leave-One-Out devuelven valores correctos (> 0).

Ejecutar: python scripts/seed_users.py
Requiere: pip install psycopg2-binary bcrypt
"""

import psycopg2
import bcrypt
import random
import urllib.request
import json
from datetime import datetime, timedelta

# ── Config ──────────────────────────────────────────────────────────────────
DB = {
    "host": "localhost",
    "port": 5433,
    "dbname": "smartbooks",
    "user": "smartbooks",
    "password": "smartbooks_password",
}

ML_METRICS_URL = "http://localhost:8002/metrics?k=10&sample_size=50"

PROFILES = [
    {"name": "Lector Sci-Fi",   "primary": "Fiction-Science Fiction-General",          "secondary": "Fiction-Fantasy-General"},
    {"name": "Thriller Fan",    "primary": "Fiction-Thrillers-General",                "secondary": "Fiction-Mystery & Detective-General"},
    {"name": "Literario",       "primary": "Fiction-Literary",                         "secondary": "Fiction-General"},
    {"name": "Historiador",     "primary": "History-General",                          "secondary": "History-United States-General"},
    {"name": "Empresario",      "primary": "Business & Economics-General",             "secondary": "Self-Help-General"},
    {"name": "Cocinero",        "primary": "Cooking-General",                          "secondary": "Cooking-Methods-General"},
    {"name": "Romántico",       "primary": "Fiction-Romance-General",                  "secondary": "Fiction-Romance-Contemporary"},
    {"name": "Joven Lector",    "primary": "Juvenile Fiction-General",                 "secondary": "Juvenile Nonfiction-General"},
    {"name": "Religioso",       "primary": "Religion-Christian Life-General",          "secondary": "Religion-General"},
    {"name": "Detective Fan",   "primary": "Fiction-Mystery & Detective-General",      "secondary": "Fiction-Thrillers-Suspense"},
]

USERS_PER_PROFILE = 5   # 10 perfiles × 5 = 50 usuarios
INTERACTIONS_MIN  = 20  # mínimo para activar el algoritmo hybrid (≥10)
INTERACTIONS_MAX  = 35
PASSWORD          = "TestPass123"

# ── Helpers ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=10)).decode()

def get_book_ids(cur, genre: str, limit: int = 100) -> list:
    """
    Devuelve hasta `limit` libros distintos del género dado.

    Usa DISTINCT ON (author, base_title) para evitar que múltiples ediciones
    del mismo libro (p. ej. 15 ediciones de Harry Potter) dominen el pool
    y sesguen el perfil del usuario hacia ese único título.
    """
    cur.execute(
        """
        SELECT id FROM (
            SELECT DISTINCT ON (author, SPLIT_PART(title, ':', 1))
                id, average_rating
            FROM books
            WHERE genre = %s AND embedding IS NOT NULL
            ORDER BY author, SPLIT_PART(title, ':', 1), average_rating DESC
        ) deduped
        ORDER BY average_rating DESC
        LIMIT %s
        """,
        (genre, limit),
    )
    return [r[0] for r in cur.fetchall()]

def user_exists(cur, email: str) -> bool:
    cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
    return cur.fetchone() is not None

def create_user(cur, name: str, email: str) -> int:
    pw_hash = hash_password(PASSWORD)
    cur.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
        (name, email, pw_hash),
    )
    return cur.fetchone()[0]

def get_book_ids_by_author(cur, genre: str, author: str, exclude_ids: list = None) -> list:
    """Devuelve los ids de libros de un autor específico en un género."""
    exclude_ids = exclude_ids or []
    cur.execute(
        """
        SELECT DISTINCT ON (SPLIT_PART(title, ':', 1)) id
        FROM books
        WHERE genre = %s AND author = %s AND embedding IS NOT NULL
        ORDER BY SPLIT_PART(title, ':', 1), average_rating DESC
        """,
        (genre, author),
    )
    return [r[0] for r in cur.fetchall() if r[0] not in exclude_ids]


def get_top_authors(cur, genre: str, min_books: int = 4) -> list:
    """Devuelve autores con al menos `min_books` títulos únicos en el género."""
    cur.execute(
        """
        SELECT author, COUNT(DISTINCT SPLIT_PART(title, ':', 1)) AS unique_titles
        FROM books
        WHERE genre = %s AND author IS NOT NULL AND author != '' AND embedding IS NOT NULL
        GROUP BY author
        HAVING COUNT(DISTINCT SPLIT_PART(title, ':', 1)) >= %s
        ORDER BY unique_titles DESC
        LIMIT 20
        """,
        (genre, min_books),
    )
    return [r[0] for r in cur.fetchall()]


def seed_interactions(cur, user_id: int, history_books: list, ground_truth_book: int):
    """
    Añade interacciones con timestamps escalonados.

    Los libros del historial se insertan primero (más antiguos) y el
    ground_truth_book se inserta al final (más reciente), para que
    Leave-One-Out lo identifique como la interacción a predecir.
    """
    all_books = history_books + [ground_truth_book]
    base_time = datetime.now() - timedelta(hours=len(all_books) + 2)

    for i, book_id in enumerate(all_books):
        ts = base_time + timedelta(hours=i + 1)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")

        # El ground truth siempre tiene like (señal clara de interés)
        is_gt = (book_id == ground_truth_book)
        if is_gt:
            action = random.choices(
                ["like", "like+rate", "fav+rate"],
                weights=[30, 40, 30],
            )[0]
        else:
            action = random.choices(
                ["like", "fav", "rate", "like+rate", "fav+rate"],
                weights=[25, 20, 20, 20, 15],
            )[0]

        if "like" in action:
            cur.execute(
                "INSERT INTO likes (user_id, book_id, created_at) VALUES (%s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (user_id, book_id, ts_str),
            )

        if "fav" in action:
            cur.execute(
                "INSERT INTO favorites (user_id, book_id, created_at) VALUES (%s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (user_id, book_id, ts_str),
            )

        if "rate" in action:
            rating = 5 if is_gt else random.choices([3, 4, 5], weights=[20, 40, 40])[0]
            cur.execute(
                """INSERT INTO ratings (user_id, book_id, rating, created_at)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (user_id, book_id) DO UPDATE
                   SET rating = EXCLUDED.rating, updated_at = EXCLUDED.created_at""",
                (user_id, book_id, rating, ts_str),
            )

def check_metrics():
    """Llama al endpoint /metrics y muestra los resultados formateados."""
    print("\n" + "─" * 55)
    print("  EVALUACIÓN DEL SISTEMA DE RECOMENDACIÓN (Leave-One-Out)")
    print("─" * 55)
    try:
        with urllib.request.urlopen(ML_METRICS_URL, timeout=120) as resp:
            data = json.loads(resp.read().decode())

        hit_rate     = data.get("hit_rate", 0)
        precision    = data.get("precision_at_k", 0)
        recall       = data.get("recall_at_k", 0)
        ndcg         = data.get("ndcg_at_k", 0)
        sample_size  = data.get("sample_size", 0)
        k            = data.get("k", 10)

        def rating(val, thresholds):
            if val >= thresholds[1]: return "BUENO   ✓"
            if val >= thresholds[0]: return "ACEPTABLE"
            return "BAJO    ✗"

        print(f"  Usuarios evaluados : {sample_size}")
        print(f"  Top-K              : {k}")
        print()
        print(f"  Hit Rate@{k:<3}       : {hit_rate:.4f}  ({hit_rate*100:.1f}%)  → {rating(hit_rate, [0.10, 0.25])}")
        print(f"  Precision@{k:<3}      : {precision:.4f}            → {rating(precision, [0.010, 0.025])}")
        print(f"  Recall@{k:<3}         : {recall:.4f}  ({recall*100:.1f}%)  → {rating(recall, [0.10, 0.25])}")
        print(f"  NDCG@{k:<3}           : {ndcg:.4f}            → {rating(ndcg, [0.05, 0.15])}")
        print()
        print(f"  {data.get('message', '')}")
        print("─" * 55)

    except Exception as e:
        print(f"  [ERROR] No se pudo contactar el servicio de métricas: {e}")
        print(f"  URL: {ML_METRICS_URL}")
        print("  Asegúrate de que el ml-service está corriendo (docker compose up).")
        print("─" * 55)

# ── Main ─────────────────────────────────────────────────────────────────────

def fix_existing_timestamps(cur):
    """
    Corrige los timestamps de las interacciones de usuarios ya creados con el
    script antiguo (que insertaba todo con el mismo created_at).

    Para cada usuario, asigna timestamps escalonados (1h entre cada interacción)
    ordenando las interacciones por id (orden de inserción original).
    Solo actualiza registros donde todos los created_at del usuario son iguales.
    """
    # Usuarios cuyas interacciones tienen el mismo timestamp (script antiguo)
    cur.execute("""
        SELECT DISTINCT user_id FROM (
            SELECT user_id, MIN(created_at) AS mn, MAX(created_at) AS mx
            FROM likes GROUP BY user_id
            HAVING MAX(created_at) = MIN(created_at) AND COUNT(*) > 1
        ) t
    """)
    stale_users = [r[0] for r in cur.fetchall()]

    if not stale_users:
        return 0

    fixed = 0
    for uid in stale_users:
        # Obtener todos los book_ids de este usuario en las 3 tablas
        cur.execute("SELECT id, book_id FROM likes WHERE user_id = %s ORDER BY id", (uid,))
        likes = cur.fetchall()
        cur.execute("SELECT id, book_id FROM favorites WHERE user_id = %s ORDER BY id", (uid,))
        favs = cur.fetchall()
        cur.execute("SELECT id, book_id FROM ratings WHERE user_id = %s ORDER BY id", (uid,))
        rates = cur.fetchall()

        # Asignar timestamps escalonados: la más antigua = n horas atrás
        total = max(len(likes), len(favs), len(rates), 1)
        base = datetime.now() - timedelta(hours=total + 2)

        for i, (row_id, _) in enumerate(likes):
            ts = base + timedelta(hours=i)
            cur.execute("UPDATE likes SET created_at = %s WHERE id = %s", (ts, row_id))

        for i, (row_id, _) in enumerate(favs):
            ts = base + timedelta(hours=i)
            cur.execute("UPDATE favorites SET created_at = %s WHERE id = %s", (ts, row_id))

        for i, (row_id, _) in enumerate(rates):
            ts = base + timedelta(hours=i)
            cur.execute("UPDATE ratings SET created_at = %s, updated_at = %s WHERE id = %s", (ts, ts, row_id))

        fixed += 1

    return fixed


def delete_test_users(cur) -> int:
    """Elimina todos los usuarios de test (email @test.com) y sus interacciones."""
    cur.execute("SELECT id FROM users WHERE email LIKE '%@test.com'")
    test_ids = [r[0] for r in cur.fetchall()]
    if not test_ids:
        return 0
    id_list = test_ids  # psycopg2 usa %s con lista
    cur.execute("DELETE FROM likes     WHERE user_id = ANY(%s)", (id_list,))
    cur.execute("DELETE FROM favorites WHERE user_id = ANY(%s)", (id_list,))
    cur.execute("DELETE FROM ratings   WHERE user_id = ANY(%s)", (id_list,))
    cur.execute("DELETE FROM users     WHERE id = ANY(%s)", (id_list,))
    return len(test_ids)


def main():
    print("=" * 55)
    print("  SmartBooks — Seed de usuarios y verificación de métricas")
    print("=" * 55)
    print("\nConectando a la base de datos...")

    conn = psycopg2.connect(**DB)
    cur  = conn.cursor()

    # Recrear siempre los usuarios de test para garantizar perfiles limpios
    print("Eliminando usuarios de test anteriores...")
    deleted = delete_test_users(cur)
    conn.commit()
    if deleted:
        print(f"  ✓ {deleted} usuarios de test eliminados (perfiles recreados)")
    else:
        print("  ✓ No había usuarios de test previos")

    created = 0
    skipped = 0

    for profile in PROFILES:
        # Pool general deduplicado (sin ediciones múltiples del mismo título)
        primary_pool   = get_book_ids(cur, profile["primary"],   120)
        secondary_pool = get_book_ids(cur, profile["secondary"],  50)
        general_pool   = list(set(primary_pool + secondary_pool))

        # Autores con ≥5 títulos únicos en el género primario, para tener
        # hasta 6 libros en el historial y 1 como ground truth
        top_authors = get_top_authors(cur, profile["primary"], min_books=5)

        if not general_pool:
            print(f"  [WARN] Sin libros para '{profile['primary']}', saltando")
            continue

        for i in range(1, USERS_PER_PROFILE + 1):
            slug  = profile["name"].lower().replace(" ", "")
            email = f"{slug}{i}@test.com"
            name  = f"{profile['name']} #{i}"

            # Elegir un autor "favorito" para este usuario (si hay disponibles)
            focus_author = random.choice(top_authors) if top_authors else None
            author_books = (
                get_book_ids_by_author(cur, profile["primary"], focus_author)
                if focus_author else []
            )

            if focus_author and len(author_books) >= 5:
                # Historial: 5-6 libros del autor favorito + pocos aleatorios de relleno.
                # Más libros del mismo autor = perfil más concentrado = señal más fuerte
                # para predecir el ground truth (otro libro del mismo autor).
                random.shuffle(author_books)
                n_author = min(len(author_books) - 1, 6)  # máx 6, reservar 1 para GT
                author_in_history = author_books[:n_author]
                ground_truth_book = author_books[n_author]  # el siguiente, sin ver

                # Completar con pocos libros aleatorios (5-10) para simular diversidad
                # sin diluir la señal del autor favorito
                extra = [b for b in general_pool
                         if b not in author_in_history and b != ground_truth_book]
                random.shuffle(extra)
                n_extra = random.randint(5, 10)
                history_books = author_in_history + extra[:n_extra]
            else:
                # Fallback: historial aleatorio, ground truth = último del pool
                random.shuffle(general_pool)
                n = random.randint(INTERACTIONS_MIN, INTERACTIONS_MAX)
                history_books = general_pool[:n]
                ground_truth_book = general_pool[n] if len(general_pool) > n else general_pool[-1]
                if ground_truth_book in history_books:
                    candidates = [b for b in general_pool if b not in history_books]
                    ground_truth_book = candidates[0] if candidates else history_books[-1]

            uid = create_user(cur, name, email)
            seed_interactions(cur, uid, history_books, ground_truth_book)

            author_info = f"autor: {focus_author[:25]}" if focus_author else "aleatorio"
            print(f"  [OK]   {email} (id={uid}) — {len(history_books)+1} ints | {author_info}")
            created += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✓ Usuarios creados: {created}  |  Saltados (ya existían): {skipped}")

    print("\nConsultando métricas al servicio de ML...")
    check_metrics()

if __name__ == "__main__":
    main()
