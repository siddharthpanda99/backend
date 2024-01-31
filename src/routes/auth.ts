import { Router, Request, Response } from 'express'
const authRouter = Router();
import { loginUserValidation, allValidatorsPassed } from 'validators/index';

import { loginUser, signUpUser } from "controllers/auth";

authRouter.route('/signup').post(signUpUser);

authRouter.route('/login').post(loginUserValidation, allValidatorsPassed, loginUser);

export default authRouter;