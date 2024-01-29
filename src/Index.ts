// src/index.js
import express, { Express, Request, Response } from "express";
import dotenv from "dotenv";

import pool from "./config";
import { authRouter, hotelsRouter, userRouter } from "./routes";
import { warn } from "console";
import { Logger } from "middlewares/Logger";
import cors from 'cors';
// import {appLogger} from "middlewares/Logger";
import { notFoundHandler } from "middlewares/NotFoundHandler";
import { errorHandler } from "middlewares/ErrorHandler";

dotenv.config();

const app: Express = express();
const port = process.env.PORT || 3000;

// Add a list of allowed origins.
// If you have more origins you would like to add, you can add them to the array below.
const allowedOrigins = ['http://localhost:5173'];

const options: cors.CorsOptions = {
    origin: allowedOrigins
};

// Then pass these options to cors:
app.use(cors(options));

app.use(express.json());
app.use(Logger);
app.get("/", (req: Request, res: Response) => {
    res.send("Express + TypeScript Server");
});

app.use("/api/v1", authRouter);
app.use("/api/v1", hotelsRouter);
app.use("/api/v1", userRouter);

app.use(errorHandler)
app.use(notFoundHandler);


app.listen(port, () => {
    console.log(`[server]: Server is running at http://localhost:${port}`);
});

