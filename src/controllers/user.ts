import { Request, Response, NextFunction } from "express";

const updateUser = (req: Request, res: Response) => {
    const userId = req.params.userId;
    res.send({ message: `Updated user by id: ${userId}` })
}

export { updateUser };