import { Client } from 'minio';

const MINIO_ENDPOINT   = process.env.MINIO_ENDPOINT   || 'minio';
const MINIO_PORT       = parseInt(process.env.MINIO_PORT || '9000', 10);
const MINIO_ACCESS_KEY = process.env.MINIO_ACCESS_KEY  || 'minioadmin';
const MINIO_SECRET_KEY = process.env.MINIO_SECRET_KEY  || 'minioadmin123';

/** Bucket donde se guardan las métricas del modelo de recomendación. */
export const METRICS_BUCKET = 'yield-predict';

/** @type {import('minio').Client | null} */
let _client = null;

/**
 * Devuelve (o crea) el cliente MinIO singleton.
 * @returns {import('minio').Client}
 */
export function getMinioClient() {
  if (!_client) {
    _client = new Client({
      endPoint:  MINIO_ENDPOINT,
      port:      MINIO_PORT,
      useSSL:    false,
      accessKey: MINIO_ACCESS_KEY,
      secretKey: MINIO_SECRET_KEY,
    });
  }
  return _client;
}

/**
 * Asegura que un bucket existe; lo crea si no.
 * @param {string} [bucketName]
 */
export async function ensureBucket(bucketName = METRICS_BUCKET) {
  const client = getMinioClient();
  const exists = await client.bucketExists(bucketName);
  if (!exists) {
    await client.makeBucket(bucketName, 'us-east-1');
  }
}

/**
 * Sube un objeto JSON al bucket de MinIO.
 *
 * @param {string} objectName  - Ruta del objeto, ej: "123/metrics/metrics_2024-01-01.json"
 * @param {object} data        - Objeto que se serializa como JSON
 * @param {string} [bucketName]
 */
export async function uploadJson(objectName, data, bucketName = METRICS_BUCKET) {
  await ensureBucket(bucketName);
  const client  = getMinioClient();
  const content = Buffer.from(JSON.stringify(data, null, 2), 'utf-8');
  await client.putObject(bucketName, objectName, content, content.length, {
    'Content-Type': 'application/json',
  });
}
