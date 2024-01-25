import { Request, Response, NextFunction } from "express";
import UserHotelRoomBookingJson from "fake/UserHotelRoomBooking.json";


const updateUser = (req: Request, res: Response) => {
    const userId = req.params.userId;
    res.send({ message: `Updated user by id: ${userId}` })
}

const checkUserBookings = (req: Request, res: Response) => {
    const userId = parseInt(req.params.userId);
    console.log("🚀 ~ checkUserBookings ~ userId:", userId)
    const bookings = UserHotelRoomBookingJson.filter((booking) => booking.user_id === userId)
    res.send({ data: bookings, message: `List of bookings for : ${userId}` })
}

export { updateUser, checkUserBookings };