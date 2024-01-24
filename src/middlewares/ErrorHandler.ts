import { ErrorRequestHandler, Request, Response, NextFunction } from "express";
import {
    BadRequestError,
    NotFoundError,
    UnAuthorizedError,
    ValidationError,
} from "../errors";

const errorHandlerMiddleWare: ErrorRequestHandler = async (
    err,
    req: Request,
    res: Response,
    next: NextFunction
) => {
    if (err.errorName === "ValidationError") {
        const errorObj = err.errors.reduce(
            (prev: any, validationError: ValidationError) => {
                return {
                    ...prev,
                    [validationError.fieldName]: validationError.message,
                };
            },
            {}
        );
        return res.status(err.statusCode).json(errorObj);
    }
    if (
        err instanceof BadRequestError ||
        err instanceof UnAuthorizedError ||
        err instanceof NotFoundError
    ) {
        return res.status(err.statusCode).json({ message: err.message });
    }
    return res
        .status(500)
        .json({ message: "something went wrong please try again later" });
};

export default errorHandlerMiddleWare;