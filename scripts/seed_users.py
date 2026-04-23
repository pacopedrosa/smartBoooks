"""
Seed de usuarios ficticios con interacciones variadas para probar el algoritmo hybrid.
Ejecutar: python scripts/seed_users.py
Requiere: pip install psycopg2-binary bcrypt
"""

import psycopg2
import bcrypt
import random
import sys

# ── Config ──────────────────────────────────────────────────────────────────
DB = {
    "host": "localhost",
    "port": 5433,
    "dbname": "smartbooks",
    "user": "smartbooks",
    "password": "smartbooks_password",
}

# Perfiles de usuario por género preferido
# Cada perfil tiene géneros primario y secundario para simular gustos reales
PROFILES = [
    {"name": "Lector Sci-Fi",     "primary": "Science-Fiction-Fantasy-Horror", "secondary": "Teen-Young-Adult"},
    {"name": "Historiador",       "primary": "History-Archaeology",             "secondary": "Society-Social-Sciences"},
    {"name": "Empresario",        "primary": "Business-Finance-Law",            "secondary": "Mind-Body-Spirit"},
    {"name": "Cocinero",          "primary": "Food-Drink",                      "secondary": "Home-Garden"},
    {"name": "Naturalista",       "primary": "Natural-History",                 "secondary": "Science-Geography"},
    {"name": "Poeta",             "primary": "Poetry-Drama",                    "secondary": "Humour"},
    {"name": "Salud Total",       "primary": "Health",                          "secondary": "Mind-Body-Spirit"},
    {"name": "Manualidades",      "primary": "Crafts-Hobbies",                  "secondary": "Home-Garden"},
    {"name": "Medico",            "primary": "Medical",                         "secondary": "Health"},
    {"name": "Joven Lector",      "primary": "Teen-Young-Adult",                "secondary": "Science-Fiction-Fantasy-Horror"},
]

USERS_PER_PROFILE = 3   # 10 perfiles × 3 = 30 usuarios nuevos
INTERACTIONS_MIN  = 15
INTERACTIONS_MAX  = 30
PASSWORD          = "TestPass123"

# ── Helpers ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=10)).decode()

def get_book_ids(cur, genre: str, limit: int = 80) -> list[int]:
    cur.execute(
        "SELECT id FROM books WHERE genre = %s ORDER BY average_rating DESC LIMIT %s",
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

def seed_interactions(cur, user_id: int, pool: list[int], n: int):
    """Añade n interacciones aleatorias (like, fav, rating) sobre el pool de libros."""
    sample = random.sample(pool, min(n, len(pool)))

    for i, book_id in enumerate(sample):
        action = random.choices(
            ["like", "fav", "rate", "like+rate", "fav+rate"],
            weights=[25, 20, 20, 20, 15],
        )[0]

        if "like" in action:
            cur.execute(
                "INSERT INTO likes (user_id, book_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, book_id),
            )

        if "fav" in action:
            cur.execute(
                "INSERT INTO favorites (user_id, book_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, book_id),
            )

        if "rate" in action:
            # Distribución realista: mayoría buenas valoraciones (3-5★)
            rating = random.choices([1, 2, 3, 4, 5], weights=[3, 7, 20, 40, 30])[0]
            cur.execute(
                """INSERT INTO ratings (user_id, book_id, rating)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (user_id, book_id) DO UPDATE SET rating = EXCLUDED.rating""",
                (user_id, book_id, rating),
            )

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Conectando a la base de datos...")
    conn = psycopg2.connect(**DB)
    cur  = conn.cursor()

    created = 0
    skipped = 0

    for profile in PROFILES:
        primary_pool   = get_book_ids(cur, profile["primary"],   80)
        secondary_pool = get_book_ids(cur, profile["secondary"],  40)
        combined_pool  = primary_pool + secondary_pool

        if not combined_pool:
            print(f"  [WARN] No hay libros para '{profile['primary']}', saltando")
            continue

        for i in range(1, USERS_PER_PROFILE + 1):
            slug  = profile["name"].lower().replace(" ", "")
            email = f"{slug}{i}@test.com"
            name  = f"{profile['name']} #{i}"

            if user_exists(cur, email):
                print(f"  [SKIP] {email} ya existe")
                skipped += 1
                continue

            uid = create_user(cur, name, email)
            n   = random.randint(INTERACTIONS_MIN, INTERACTIONS_MAX)
            seed_interactions(cur, uid, combined_pool, n)

            print(f"  [OK]  {email} (id={uid}) — {n} interacciones | género: {profile['primary']}")
            created += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✓ Usuarios creados: {created}  |  Saltados (ya existían): {skipped}")

    if created > 0:
        print("\nAhora prueba las recomendaciones de paco@gmail.com con el algoritmo hybrid:")
        print("  Las interacciones de los nuevos usuarios alimentan el filtrado colaborativo.")
        print("  Si paco tiene ≥10 interacciones y hay solapamiento de libros → algoritmo: hybrid")

if __name__ == "__main__":
    main()
