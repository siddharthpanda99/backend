import { Request, Response, NextFunction } from "express";
import { User } from "types/User";
import { users } from "fake/Users";

const signUpUser = (req: Request, res: Response) => {
    const body: User = req.body;
    if(!body.username || !body.password){
        res.status(403).send({ data: {}, message: 'Please enter username and/or password' })
    }
    else res.status(200).send({ data: body, message: 'User signed up successfully'})
}

const loginUser = (req: Request, res: Response) => {
    const body: User = req.body;
    if (!body.email || !body.password) {
        res.status(403).send({ data: {}, message: 'Please enter username and/or password' })
    } else {

        const req_user = users.find(user => user.email === body.email && user.password === body.password)
        if(req_user){
            res.status(200).send({ message: 'User logged in successfully' })
        } else {
            res.status(200).send({ message: 'Check email/password' })
        }
    }
}

export { signUpUser, loginUser };