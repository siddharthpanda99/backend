import { Request, Response, NextFunction } from "express";
import UserHotelRoomBookingJson from "fake/UserHotelRoomBooking.json";


const updateUser = (req: Request, res: Response) => {
    const userId = req.params.userId;
    res.send({ message: `Updated user by id: ${userId}` })
}

const checkUserBookings = (req: Request, res: Response) => {
    const query = req.query;
    const bookings = UserHotelRoomBookingJson.filter((booking) => booking.user_email === query.email)
    console.log("🚀 ~ checkUserBookings ~ bookings:", bookings, query.email)
    if(bookings?.length){
        res.status(200).send({ data: bookings, message: `List of bookings for : ${query.email}` })
    } else {
        res.status(204).send({ data: [], message: `No bookings found for : ${query.email}` })
    }
    
}

export { updateUser, checkUserBookings };