import { CustomValidator, body } from 'express-validator';
import hotels from 'fake/Hotels.json'
import { Hotel } from "types/Hotel";
import { users } from 'fake/Users';
import { User } from 'types/User';

const hotelExists: CustomValidator = async (hotelId: number) => {
    // Query the database to check if the hotel with the given ID exists
    const hotel: Hotel | undefined = hotels.find(hotel => {
        return hotel.id === hotelId
    })

    if (!hotel) {
        return Promise.reject('The entered hotel id does not exist');
    }

    // If the hotel exists, resolve the promise
    return Promise.resolve();
};

const userExists: CustomValidator = async (user_email: string) => {
    // Query the database to check if the hotel with the given ID exists
    const user: User | undefined = users.find(usr => {
        return usr.email === user_email
    })

    if (!user) {
        return Promise.reject('The entered user does not exist');
    }

    // If the hotel exists, resolve the promise
    return Promise.resolve();
};

const dateValidator: CustomValidator = (value: string, { req }) => {
    const checkInDate = Date.parse(req.body.check_in_date);
    console.log("🚀 ~ checkInDate:", checkInDate, req.body.check_in_date)
    const checkOutDate = Date.parse(req.body.check_out_date);
    console.log("🚀 ~ checkOutDate:", checkOutDate, req.body.check_out_date)

    // Check that check_in_date and check_out_date are not the same
    if (checkInDate === checkOutDate) {
        throw new Error('Check-in date and check-out date cannot be the same');
    }

    // Check that check_out_date comes after check_in_date
    if (checkOutDate < checkInDate) {
        throw new Error('Check-out date must come after check-in date');
    }

    // Check that both check_in_date and check_out_date are not in the past
    const currentDate = Date.now();
    console.log("🚀 ~ currentDate:", currentDate)
    if (checkInDate < currentDate || checkOutDate < currentDate) {
        throw new Error('Check-in and check-out dates must be in the future');
    }
};

export const UserBookingValidation = [
    body('hotel_id')
        .notEmpty().withMessage('Please enter the id for hotel you are booking for').custom(hotelExists),
    body('check_in_date')
        .notEmpty().withMessage('Please enter your check_in_date').custom(dateValidator),
    body('check_out_date')
        .notEmpty().withMessage('Please enter your check_out_date').custom(dateValidator),
    body('room_id')
        .notEmpty().withMessage('Please enter your room_id'),
    body('total_amount')
        .notEmpty().withMessage('Please enter your total_amount'),
    body('user_email')
        .notEmpty().withMessage('Please enter your email')
        .isEmail().withMessage('Please enter a valid email address')
        .custom(userExists),
];
