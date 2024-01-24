import dotenv from "dotenv";
dotenv.config();
import { PoolConfig } from "pg"

export const POOL_CONFIG: PoolConfig = {
    database: process.env.POSTGRES_DB_NAME,
    user: process.env.POSTGRES_USER,
    password: process.env.POSTGRES_PASSWORD,
    port: Number(process.env.PGPORT),
    host: process.env.POSTGRES_DB_HOST,
    max: Number(process.env.DB_POOL_SIZE),
    idleTimeoutMillis: Number(process.env.DB_POOL_CLIENT_IDLE_TIMEOUT),
    connectionTimeoutMillis: Number(process.env.DB_POOL_CLIENT_CONNECTION_TIMEOUT),
};