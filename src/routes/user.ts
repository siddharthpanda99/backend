import { Router, Request, Response } from 'express'
const userRouter = Router();

import { checkUserBookings } from "controllers/user";

userRouter.route('/bookings/user/:userId').get(checkUserBookings);

export default userRouter;