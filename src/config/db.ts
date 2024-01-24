import { Pool } from "pg";
import { POOL_CONFIG } from "./variables";

const pool = new Pool(POOL_CONFIG);

export default pool;