import { Router, Request, Response } from 'express'
const authRouter = Router();
import { loginUserValidation, validateLoginUser } from 'validators/authValidators';

import { loginUser, signUpUser } from "controllers/auth";

authRouter.route('/signup').post(signUpUser);

authRouter.route('/login').post(loginUserValidation, validateLoginUser, loginUser);

export default authRouter;