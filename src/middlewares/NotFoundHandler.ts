import express, { Request, Response, NextFunction } from "express";

export const notFoundHandler = (req: Request, res: Response, next: NextFunction) => {
    res.status(404).json({
        error: 404,
        message: "Route not found."
    })
}