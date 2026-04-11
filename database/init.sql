-- ============================================================
-- SmartBooks — Esquema de base de datos
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS books (
    id             SERIAL PRIMARY KEY,
    title          VARCHAR(255) NOT NULL,
    author         VARCHAR(255) NOT NULL,
    genre          VARCHAR(100),
    description    TEXT,
    cover_url      VARCHAR(500),
    isbn           VARCHAR(20),
    published_year INTEGER,
    pages          INTEGER,
    language       VARCHAR(50) DEFAULT 'Español',
    average_rating DECIMAL(3,2) DEFAULT 0,
    total_ratings  INTEGER DEFAULT 0,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS likes (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    book_id    INTEGER REFERENCES books(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, book_id)
);

CREATE TABLE IF NOT EXISTS favorites (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    book_id    INTEGER REFERENCES books(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, book_id)
);

CREATE TABLE IF NOT EXISTS ratings (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    book_id    INTEGER REFERENCES books(id) ON DELETE CASCADE,
    rating     INTEGER CHECK (rating >= 1 AND rating <= 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, book_id)
);

-- ============================================================
-- Índices para optimizar consultas frecuentes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_likes_user_id    ON likes(user_id);
CREATE INDEX IF NOT EXISTS idx_likes_book_id    ON likes(book_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user   ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_book   ON favorites(book_id);
CREATE INDEX IF NOT EXISTS idx_ratings_user     ON ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_book     ON ratings(book_id);
CREATE INDEX IF NOT EXISTS idx_books_genre      ON books(genre);

-- ============================================================
-- Datos iniciales — Catálogo de libros
-- ============================================================
INSERT INTO books (title, author, genre, description, published_year, pages, language) VALUES
('El nombre del viento',              'Patrick Rothfuss',         'Fantasía',         'La historia de Kvothe, un joven huérfano que se convierte en uno de los magos más legendarios de su tiempo. Primera parte de la Crónica del Asesino de Reyes.',                                           2007, 662,  'Español'),
('Cien años de soledad',              'Gabriel García Márquez',   'Realismo Mágico',  'La saga multigeneracional de la familia Buendía en el mítico pueblo de Macondo, obra cumbre del realismo mágico latinoamericano.',                                                                        1967, 432,  'Español'),
('1984',                              'George Orwell',             'Distopía',         'En una sociedad totalitaria dominada por el Gran Hermano, Winston Smith trabaja en el Ministerio de la Verdad reescribiendo la historia.',                                                                  1949, 328,  'Español'),
('El Señor de los Anillos',           'J.R.R. Tolkien',           'Fantasía',         'La épica aventura de Frodo Bolsón y la Comunidad del Anillo para destruir el Anillo Único y derrotar al oscuro señor Sauron.',                                                                             1954, 1137, 'Español'),
('Harry Potter y la Piedra Filosofal','J.K. Rowling',             'Fantasía',         'El primer año de Harry Potter en el Colegio Hogwarts de Magia y Hechicería. El inicio de una saga mundial sobre magia, amistad y valentía.',                                                             1997, 309,  'Español'),
('Dune',                              'Frank Herbert',             'Ciencia Ficción',  'En el planeta desértico Arrakis, el único lugar donde se produce la especia más valiosa del universo, Paul Atreides se convierte en el mesías de los Fremen.',                                           1965, 688,  'Español'),
('El código Da Vinci',                'Dan Brown',                 'Thriller',         'El profesor Robert Langdon investiga un asesinato en el Louvre que le lleva a descubrir una conspiración que sacude los cimientos del cristianismo.',                                                     2003, 454,  'Español'),
('La sombra del viento',              'Carlos Ruiz Zafón',        'Misterio',         'En la Barcelona de posguerra, un niño descubre un libro misterioso en el Cementerio de los Libros Olvidados que cambiará su vida para siempre.',                                                          2001, 560,  'Español'),
('Fundación',                         'Isaac Asimov',              'Ciencia Ficción',  'Hari Seldon desarrolla la psicohistoria, una ciencia que predice el futuro, y crea la Fundación para preservar el conocimiento de la humanidad.',                                                         1951, 255,  'Español'),
('El Alquimista',                     'Paulo Coelho',              'Ficción',          'Santiago, un joven pastor andaluz, viaja desde España hasta Egipto en busca de su leyenda personal, aprendiendo que el tesoro está dentro de uno mismo.',                                                 1988, 208,  'Español'),
('Sapiens',                           'Yuval Noah Harari',         'No Ficción',       'Una ambiciosa historia de la humanidad que recorre 70.000 años de historia desde el surgimiento del Homo sapiens hasta la era digital.',                                                                  2011, 443,  'Español'),
('El Hobbit',                         'J.R.R. Tolkien',           'Fantasía',         'Bilbo Bolsón, un hobbit tranquilo que nunca ha tenido aventuras, es arrastrado por el mago Gandalf a una expedición inesperada para recuperar el tesoro del dragón Smaug.',                              1937, 310,  'Español'),
('Neuromante',                        'William Gibson',            'Ciencia Ficción',  'Un hacker expulsado de la red y una asesina cibernética son contratados para llevar a cabo el mayor robo informático de la historia en el ciberespacio.',                                                1984, 271,  'Español'),
('Matar un ruiseñor',                 'Harper Lee',                'Drama',            'En Alabama durante los años 30, el abogado Atticus Finch defiende a un hombre negro injustamente acusado de un crimen que no cometió.',                                                                   1960, 336,  'Español'),
('El gran Gatsby',                    'F. Scott Fitzgerald',      'Drama',            'La historia de Jay Gatsby y su obsesión por Daisy Buchanan en el Nueva York de los locos años 20, una crítica al sueño americano.',                                                                        1925, 218,  'Español'),
('Orgullo y Prejuicio',               'Jane Austen',               'Romance',          'Elizabeth Bennet, la segunda de cinco hermanas, navega las exigencias de la sociedad inglesa del siglo XIX en busca del amor verdadero.',                                                                 1813, 432,  'Español'),
('Don Quijote de la Mancha',          'Miguel de Cervantes',      'Clásico',          'Las aventuras del hidalgo Alonso Quijano que, enloquecido por las novelas de caballerías, decide convertirse en caballero andante junto a su escudero Sancho Panza.',                                    1605, 1023, 'Español'),
('Crimen y Castigo',                  'Fiódor Dostoyevski',       'Drama',            'Raskolnikov, un estudiante ruso empobrecido, comete un asesinato creyendo estar por encima de la moral común y debe enfrentarse a las consecuencias psicológicas.',                                       1866, 671,  'Español'),
('Un mundo feliz',                    'Aldous Huxley',             'Distopía',         'Una sociedad futura donde la estabilidad social se mantiene mediante el condicionamiento genético, los fármacos y el consumismo desenfrenado.',                                                            1932, 311,  'Español'),
('El Principito',                     'Antoine de Saint-Exupéry', 'Ficción',          'Un piloto varado en el desierto del Sahara conoce a un pequeño príncipe caído de un asteroide que le enseña a ver con el corazón.',                                                                       1943, 96,   'Español'),
('Fahrenheit 451',                    'Ray Bradbury',              'Distopía',         'En un futuro donde los libros están prohibidos y los bomberos los queman, Guy Montag comienza a dudar del mundo que lo rodea.',                                                                            1953, 256,  'Español'),
('La metamorfosis',                   'Franz Kafka',               'Clásico',          'Gregor Samsa amanece un día convertido en un monstruoso insecto, explorando temas de alienación, identidad y las exigencias de la familia y la sociedad.',                                               1915, 98,   'Español'),
('El juego de Ender',                 'Orson Scott Card',          'Ciencia Ficción',  'Andrew "Ender" Wiggin, un niño superdotado, es reclutado para la Escuela de Batalla donde se prepara a la humanidad para su guerra final contra los insectores.',                                        1985, 352,  'Español'),
('Crónica de una muerte anunciada',   'Gabriel García Márquez',   'Realismo Mágico',  'El crónico relato de un crimen anunciado en un pueblo latinoamericano donde todos sabían lo que iba a pasar pero nadie lo impidió.',                                                                       1981, 120,  'Español'),
('Los juegos del hambre',             'Suzanne Collins',           'Distopía',         'En el futuro país de Panem, Katniss Everdeen es seleccionada para participar en los Juegos del Hambre, un brutal reality show donde los participantes luchan hasta la muerte.',                           2008, 374,  'Español');
