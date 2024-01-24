import { Request, Response, NextFunction } from "express";
import { User } from "types/User";

const signUpUser = (req: Request, res: Response) => {
    const body: User = req.body;
    if(!body.username || !body.password){
        res.status(403).send({ data: {}, message: 'Please enter username and/or password' })
    }
    else res.status(200).send({ data: body, message: 'User signed up successfully'})
}

const loginUser = (req: Request, res: Response) => {
    res.status(200).send({message: 'User logged in successfully'})
}

export { signUpUser, loginUser };