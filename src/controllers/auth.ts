import { Request, Response, NextFunction } from "express";
import { User } from "types/User";

const signUpUser = (req: Request, res: Response) => {
    const body: User = req.body;
    if(!body.username || !body.password){
        res.send({ data: {}, message: 'Please enter username and/or password' })
    }
    res.send ({ data: body, message: 'User signed up successfully'})
}

const loginUser = (req: Request, res: Response) => {
    res.send({message: 'User logged in successfully'})
}

export { signUpUser, loginUser };