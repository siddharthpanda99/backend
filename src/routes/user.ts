import { Router, Request, Response } from 'express'
const userRouter = Router();

import { updateUser } from "controllers/user";

userRouter.route('/update/:userId').patch(updateUser);

export default userRouter;