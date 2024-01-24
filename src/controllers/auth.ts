import { Request, Response, NextFunction } from "express";

const signUpUser = (req: Request, res: Response) => {
    res.send ({ message: 'User signed up successfully'})
}

const loginUser = (req: Request, res: Response) => {
    res.send({message: 'User logged in successfully'})
}

export { signUpUser, loginUser };