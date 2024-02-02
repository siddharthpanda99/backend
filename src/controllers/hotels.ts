import fs from 'fs';
import { Request, Response, NextFunction } from "express";
import hotels from 'fake/Hotels.json'
import { getHotelDetailsById } from "src/utils/getHotelById";
import { UserHotelRoomBooking } from "types/RoomBooking";
import { areDatesAlreadyBlocked, isUniqueBooking } from 'src/utils/Booking';
import { SortFilterOptions } from 'src/utils/sortFilter';
import { sortAndFilterList } from 'src/utils/sortFilter';
import { PrismaClient } from '@prisma/client';

/**
 * Retrieves a list of hotels.
 *
 * @function
 * @async
 * @param {express.Request} req - Express request object.
 * @param {express.Response} res - Express response object.
 * @returns {Promise<void>} - A Promise that resolves once the operation is complete.
 *
 * @throws {Error} Will throw an error if there is a problem processing the request.
 *
 * @description
 * This function is responsible for retrieving a list of hotels and sending it as a response.
 *
 * @example
 * // Successful response:
 * // {
 * //   "data": [
 * //     {
 * //       "id": 1,
 * //       "name": "Hotel A",
 * //       "location": "City X",
 * //       "price": 150,
 * //       "rating": 4,
 * //       "rooms": []
 * //     },
 * //     {
 * //       "id": 2,
 * //       "name": "Hotel B",
 * //       "location": "City Y",
 * //       "price": 200,
 * //       "rating": 5,
 * //       "rooms": []
 * //     },
 * //     // ... other hotels
 * //   ],
 * //   "message": "Fetched a list of hotels"
 * // }
 *
 * // Failed response (if any):
 * // {
 * //   "message": "An error occurred while fetching hotels."
 * // }
 */
// http://localhost:8000/api/v1/hotels?sortField=rating&sortOrder=descsortField=price&sortOrder=desc&filters[location]=Countryside&filters[location]=Countryside&filters[location]=Downtown
const getListOfHotels = async (req: Request, res: Response) => {
    const options:SortFilterOptions = {
        sortFields: req.query.sortField as string,
        sortOrder: req.query.sortOrder as 'asc' | 'desc',
        filters: req.query.filters as Record<string, any>,
    };
    const prisma = new PrismaClient()
    console.log("🚀 ~ getListOfHotels ~ options:", options)
    const hotels = await prisma.hotel.findMany();
    console.log("🚀 ~ getListOfHotels ~ hotels:", hotels)
    // const sortedAndFilteredItems = sortAndFilterList(hotels, options);

    res.send({ data: hotels, message: 'Fetched a list of hotels' })
}


/**
 * Retrieves details of a hotel by its ID.
 *
 * @function
 * @async
 * @param {express.Request} req - Express request object.
 * @param {express.Response} res - Express response object.
 * @returns {Promise<void>} - A Promise that resolves once the operation is complete.
 *
 * @throws {Error} Will throw an error if there is a problem processing the request.
 *
 * @description
 * This function is responsible for retrieving details of a hotel by its ID and sending it as a response.
 *
 * @param {number} req.params.hotelId - The ID of the hotel to retrieve.
 *
 * @example
 * // Sample URL: /hotels/1
 *
 * // Successful response:
 * // {
 * //   "data": {
 * //     "id": 1,
 * //     "name": "Hotel A",
 * //     "location": "City X",
 * //     "price": 150,
 * //     "rating": 4,
 * //     "rooms": []
 * //   },
 * //   "message": "Fetched hotel by id: 1"
 * // }
 *
 * // Failed response (if hotel with the specified ID is not found):
 * // {
 * //   "message": "Hotel not found for the provided ID."
 * // }
 */
const getHotelById = (req: Request, res: Response) => {
    const hotelId = req.params.hotelId;
    const hotelDetails = getHotelDetailsById(hotelId)
    res.send({ data: hotelDetails ,message: `Fetched hotel by id: ${hotelId}` })
}


/**
 * Handles hotel room booking.
 *
 * @function
 * @async
 * @param {express.Request} req - Express request object.
 * @param {express.Response} res - Express response object.
 * @returns {Promise<void>} - A Promise that resolves once the operation is complete.
 *
 * @throws {Error} Will throw an error if there is a problem processing the request.
 *
 * @description
 * This function is responsible for handling hotel room booking requests. It validates the provided
 * booking details, checks for uniqueness, and updates the booking information if the conditions are met.
 *
 * @param {Object} req.body - The booking details.
 * @param {number} req.body.room_id - The ID of the room to be booked.
 * @param {Date} req.body.check_in_date - The check-in date for the booking.
 * @param {Date} req.body.check_out_date - The check-out date for the booking.
 * @param {number} req.body.total_amount - The total amount for the booking.
 * @param {string} req.body.user_email - The email of the user making the booking.
 * @param {number} req.body.hotel_id - The ID of the hotel for which the room is being booked.
 *
 * @example
 * // Sample request body:
 * // {
 * //   "room_id": 1,
 * //   "check_in_date": "1997-07-16T19:20+01:00",
 * //   "check_out_date": "1997-07-16T19:20+01:00",
 * //   "total_amount": 1000,
 * //   "user_email": "test@test.com",
 * //   "hotel_id": 1
 * // }
 *
 * // Successful response:
 * // {
 * //   "data": {
 * //     "booking_id": 123,
 * //     "room_id": 1,
 * //     "check_in_date": "1997-07-16T19:20+01:00",
 * //     "check_out_date": "1997-07-16T19:20+01:00",
 * //     "total_amount": 1000,
 * //     "user_email": "test@test.com",
 * //     "hotel_id": 1
 * //   },
 * //   "message": "Hotel Booked successfully"
 * // }
 *
 * // Failed response (if room is already booked by the user):
 * // {
 * //   "message": "You have already booked this room"
 * // }
 *
 * // Failed response (if dates are already booked for the room):
 * // {
 * //   "message": "The dates for which you have booked are not available"
 * // }
 */
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
    body.booking_id = BookingsList.length ? BookingsList[BookingsList?.length - 1]?.booking_id + 1 : 1
    // If combination of room, hotel, user and booking id must be unique 
    const isUnique = isUniqueBooking(BookingsList, body)
    const datesOverlapping = areDatesAlreadyBlocked(BookingsList, body)
    console.log("🚀 ~ bookHotel ~ datesOverlapping:", datesOverlapping)
    console.log("🚀 ~ bookHotel ~ isUniqueBooking:", isUnique)
    if (!isUnique){
        res.status(400).send({ data: [], message: "You have already booked this room" })
    } else if (datesOverlapping) {
        console.log("🚀 ~ bookHotel ~ areDatesAlreadyBlocked:", areDatesAlreadyBlocked)
        res.status(400).send({ data: [], message: "The dates for which you have booked are not available" })
    } else {
        BookingsList.push(body)
        fs.writeFileSync('src/fake-repository/UserHotelRoomBooking.json', JSON.stringify(BookingsList, null, 2));
        res.status(200).send({ data: body, message: "Hotel Booked successfully" })
    }

    // console.log("🚀 ~ bookHotel ~ body:", BookingsList)
}

export { getListOfHotels, getHotelById, bookHotel };