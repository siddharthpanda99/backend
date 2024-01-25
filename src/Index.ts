// src/index.js
import express, { Express, Request, Response } from "express";
import dotenv from "dotenv";

import pool from "./config";
import { authRouter, hotelsRouter, userRouter } from "./routes";
import { warn } from "console";
import { Logger } from "middlewares/Logger";
// import {appLogger} from "middlewares/Logger";
// import { notFoundMiddleware, errorHandlerMiddleWare } from "./middleware";

dotenv.config();

const app: Express = express();
const port = process.env.PORT || 3000;
app.use(express.json());
// app.use(Logger);

app.get("/", (req: Request, res: Response) => {
    res.send("Express + TypeScript Server");
});

app.use("/api/v1", authRouter);
app.use("/api/v1", hotelsRouter);
app.use("/api/v1", userRouter);


app.listen(port, () => {
    console.log(`[server]: Server is running at http://localhost:${port}`);
});

