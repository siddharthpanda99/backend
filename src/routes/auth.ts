import { Router, Request, Response } from 'express'
const authRouter = Router();

import { loginUser, signUpUser } from "../controllers/auth";

authRouter.route('/signup').post(signUpUser);
authRouter.route('/login').post(loginUser);

export default authRouter;