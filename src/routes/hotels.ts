import { Router } from 'express'
import { UserBookingValidation, allValidatorsPassed } from 'validators/index';
const hotelsRouter = Router();

import { getListOfHotels, getHotelById, bookHotel } from "controllers/hotels";

hotelsRouter.route('/hotels').get(getListOfHotels);
hotelsRouter.route('/hotels/:hotelId').get(getHotelById);
hotelsRouter.route('/book/:hotelId').post(UserBookingValidation, allValidatorsPassed, bookHotel);

export default hotelsRouter;