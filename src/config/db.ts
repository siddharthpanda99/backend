import pg from "pg";
const { Pool } = pg;
import { POOL_CONFIG } from "./variables";

const pool = new Pool(POOL_CONFIG);
// // Function to check if the database exists
// async function databaseExists(databaseName: string) {
//     const client = await pool.connect();
//     const query = "SELECT datname FROM pg_database WHERE datname = $1";
//     const result = await client.query(query, [databaseName]);
//     return result.rows.length > 0
//     // const res = client.query(`SELECT datname FROM pg_catalog.pg_database WHERE datname = '${databaseName}'`);
//     // console.log("🚀 ~ databaseExists ~ res:", res)
//     // return res?.rows.length > 0;
// }

// // Function to create the database
// export async function createDatabase() {
//     try {
//         const dbName = process.env.POSTGRES_DB_NAME;
//         console.log("🚀 ~ createDatabase ~ dbName:", dbName)

//         if (!dbName) {
//             throw new Error('DB_NAME is not defined in the environment variables.');
//         }
//         console.log("🚀 ~ createDatabase ~ Still WOrrking", )
//         // Check if the database already exists
//         const dbExists = await pool.query(`SELECT datname FROM pg_catalog.pg_database WHERE datname = '${dbName}'`);
//         console.log("🚀 ~ createDatabase ~ dbExists:", dbExists)
//         console.log("🚀 ~ createDatabase ~ dbExists:", dbExists)

//         if (!dbExists) {
//             // Create the database if it does not exist
//             const createDbQuery = `CREATE DATABASE ${dbName}`;
//             await pool.query(createDbQuery);

//             console.log(`Database "${dbName}" created successfully.`);
//         } else {
//             console.log(`Database "${dbName}" already exists. Skipping creation.`);
//         }
//     } catch (error) {
//         console.error('Error creating or checking database:', error);
//     } finally {
//         // Close the pool
//         await pool.end();
//     }
// }

export const query = async (text: string, params:any) => {
        // invocation timestamp for the query method
        const start = Date.now();
        try {
            const res = await pool.query(text, params);
            // time elapsed since invocation to execution
            const duration = Date.now() - start;
            console.log(
                'executed query',
                { text, duration, rows: res.rowCount }
            );
            return res;
        } catch (error) {
            console.log('error in query', { text });
            throw error;
        }
    }
export default pool;