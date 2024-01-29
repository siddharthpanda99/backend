import { Request, Response, NextFunction } from "express";
import UserHotelRoomBookingJson from "fake/UserHotelRoomBooking.json";
import hotels from 'fake/Hotels.json'
import roomsJson from 'fake/hotelsWithRooms.json'
import { Booking } from "types/Booking";


const updateUser = (req: Request, res: Response) => {
    const userId = req.params.userId;
    res.send({ message: `Updated user by id: ${userId}` })
}

const checkUserBookings = (req: Request, res: Response) => {
    const query = req.query;
    const bookings = UserHotelRoomBookingJson.filter((booking) => booking.user_email === query.email)
    const bookingArray = [];

    bookings.forEach(booking => {
        const hotel = hotels.find(h => h.id === booking.hotel_id);
        const room = roomsJson[booking.hotel_id].find(r => r.id === booking.room_id);
        console.log("🚀 ~ checkUserBookings ~ room:", room)

        if (hotel && room) {
            const bookingDetails = {
                booking_id: booking.booking_id,
                user_email: booking.user_email,
                check_in_date: booking.check_in_date,
                check_out_date: booking.check_out_date,
                hotel_name: hotel.name,
                room_details: {
                    type: room.type,
                    noOfRooms: room.noOfRooms,
                    amenities: room.amenities,
                },
                total_amount: room.price,
            };

            bookingArray.push(bookingDetails);
        }
    });

    console.log("🚀 ~ checkUserBookings ~ bookingArray:", bookingArray)

    // console.log("🚀 ~ checkUserBookings ~ bookings:", bookings, query.email)
    if(bookings?.length){
        res.status(200).send({ data: bookingArray, message: `List of bookings for : ${query.email}` })
    } else {
        res.status(204).send({ data: [], message: `No bookings found for : ${query.email}` })
    }
    
}

export { updateUser, checkUserBookings };