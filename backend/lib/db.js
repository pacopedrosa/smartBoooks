import { Pool } from 'pg';

/** @type {Pool | null} */
let pool = null;

function getPool() {
  if (!pool) {
    pool = new Pool({
      connectionString: process.env.DATABASE_URL,
      max: 10,
      idleTimeoutMillis: 30_000,
      connectionTimeoutMillis: 5_000,
    });
  }
  return pool;
}

/**
 * Ejecuta una consulta SQL parametrizada.
 * @param {string} text
 * @param {unknown[]} [params]
 */
export async function query(text, params) {
  const client = await getPool().connect();
  try {
    return await client.query(text, params);
  } finally {
    client.release();
  }
}
