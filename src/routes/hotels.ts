import { Router } from 'express'
const hotelsRouter = Router();

import { getListOfHotels, getHotelById, bookHotel } from "controllers/hotels";

hotelsRouter.route('/hotels').get(getListOfHotels);
hotelsRouter.route('/hotels/:hotelId').get(getHotelById);
hotelsRouter.route('/book/:hotelId').post(bookHotel);

export default hotelsRouter;