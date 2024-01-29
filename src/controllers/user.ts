import { Request, Response, NextFunction } from "express";
import UserHotelRoomBookingJson from "fake/UserHotelRoomBooking.json";
import hotels from 'fake/Hotels.json'
import roomsJson from 'fake/hotelsWithRooms.json'
import { Booking } from "types/Booking";
import { populateBookingsWithDetails } from "src/utils/Booking";


const updateUser = (req: Request, res: Response) => {
    const userId = req.params.userId;
    res.send({ message: `Updated user by id: ${userId}` })
}

const checkUserBookings = (req: Request, res: Response) => {
    const query = req.query;
    const bookings = UserHotelRoomBookingJson.filter((booking) => booking.user_email === query.email)
    const bookingArray = populateBookingsWithDetails(hotels, roomsJson, bookings)

    console.log("🚀 ~ checkUserBookings ~ bookingArray:", bookingArray)

    // console.log("🚀 ~ checkUserBookings ~ bookings:", bookings, query.email)
    if(bookings?.length){
        res.status(200).send({ data: bookingArray, message: `List of bookings for : ${query.email}` })
    } else {
        res.status(204).send({ data: [], message: `No bookings found for : ${query.email}` })
    }
    
}

export { updateUser, checkUserBookings };