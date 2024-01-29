import express, { ErrorRequestHandler, NextFunction, Request, Response } from 'express';

interface CustomError extends Error {
    status?: number;
}

export const errorHandler: ErrorRequestHandler = (err: CustomError, req: Request, res: Response, next: NextFunction) => {
    console.error('Error handler middleware triggered:', err);

    let statusCode: number = err.status || 500;
    let errorMessage: string = err.message || 'Internal Server Error';

    // Customize error messages and status codes based on error type
    switch (statusCode) {
        case 400:
            errorMessage = 'Bad Request';
            break;
        case 403:
            errorMessage = 'Forbidden';
            break;
        case 404:
            errorMessage = 'Not Found';
            break;
        // Add more cases as needed

        // Default case for other errors
        default:
            statusCode = 500;
            errorMessage = 'Internal Server Error';
    }

    // Set the response status and send a JSON response
    res.status(statusCode).json({
        error: {
            message: errorMessage,
        },
    });
};
