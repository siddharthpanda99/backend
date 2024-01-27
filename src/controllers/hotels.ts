import fs from 'fs';
import { Request, Response, NextFunction } from "express";
import hotels from 'fake/Hotels.json'
import { getHotelDetailsById } from "src/utils/getHotelById";
import { UserHotelRoomBooking } from "types/RoomBooking";
import { areDatesAlreadyBlocked, isUniqueBooking } from 'src/utils/Booking';

const getListOfHotels = (req: Request, res: Response) => {
    res.send({ data: hotels, message: 'Fetched a list of hotels' })
}

const getHotelById = (req: Request, res: Response) => {
    const hotelId = req.params.hotelId;
    const hotelDetails = getHotelDetailsById(hotelId)
    res.send({ data: hotelDetails ,message: `Fetched hotel by id: ${hotelId}` })
}

const bookHotel = (req: Request, res: Response) => {
    // Sample data
//     {
//     "room_id": 1,
//     "check_in_date": "1997-07-16T19:20+01:00",
//     "check_out_date": "1997-07-16T19:20+01:00",
//     "total_amount": 1000,
//     "user_email": "test@test.com",
//     "hotel_id": 1
// }
    const body: UserHotelRoomBooking = req.body;
    const fileBuffer = fs.readFileSync('src/fake-repository/UserHotelRoomBooking.json').toString();
    const BookingsList = JSON.parse(fileBuffer);
    console.log("🚀 ~ bookHotel ~ BookingsList:", BookingsList?.slice(-1))
    body.booking_id = BookingsList[BookingsList?.length - 1]?.booking_id + 1
    // If combination of room, hotel, user and booking id must be unique 
    const isUnique = isUniqueBooking(BookingsList, body)
    const datesOverlapping = areDatesAlreadyBlocked(BookingsList, body)
    console.log("🚀 ~ bookHotel ~ datesOverlapping:", datesOverlapping)
    console.log("🚀 ~ bookHotel ~ isUniqueBooking:", isUnique)
    if (!isUnique){
        res.send({ data: [], message: "You have already booked this room" })
    } else if (datesOverlapping) {
        console.log("🚀 ~ bookHotel ~ areDatesAlreadyBlocked:", areDatesAlreadyBlocked)
        res.send({ data: [], message: "The dates for which you have booked are not available" })
    } else {
        BookingsList.push(body)
        fs.writeFileSync('src/fake-repository/UserHotelRoomBooking.json', JSON.stringify(BookingsList, null, 2));
        res.send({ data: body, message: "Hotel Booked successfully" })
    }

    // console.log("🚀 ~ bookHotel ~ body:", BookingsList)
}

const checkBookingStatus = (req: Request, res: Response) => {
    const bookingId = req.params.bookingId;
    // console.log("🚀 ~ bookHotel ~ body:", bookingId)
    res.send({ message: bookingId })
}
export { getListOfHotels, getHotelById, bookHotel, checkBookingStatus };