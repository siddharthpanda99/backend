import { body } from 'express-validator';
import hotels from 'fake/Hotels.json'
import { Hotel } from "types/Hotel";
import { users } from 'fake/Users';
import { User } from 'types/User';

const hotelExists = async (hotelId) => {
    // Query the database to check if the hotel with the given ID exists
    const hotel: Hotel | undefined = hotels.find(hotel => {
        return hotel.id === parseInt(hotelId)
    })

    if (!hotel) {
        return Promise.reject('The entered hotel id does not exist');
    }

    // If the hotel exists, resolve the promise
    return Promise.resolve();
};

const userExists = async (user_email) => {
    // Query the database to check if the hotel with the given ID exists
    const user: User | undefined = users.find(usr => {
        return usr.id === user_email
    })

    if (!user) {
        return Promise.reject('The entered user does not exist');
    }

    // If the hotel exists, resolve the promise
    return Promise.resolve();
};

export const UserBookingValidation = [
    body('hotel_id')
        .notEmpty().withMessage('Please enter the id for hotel you are booking for').custom(hotelExists),
    body('check_in_date')
        .notEmpty().withMessage('Please enter your check_in_date'),
    body('check_out_date')
        .notEmpty().withMessage('Please enter your check_out_date'),
    body('room_id')
        .notEmpty().withMessage('Please enter your room_id'),
    body('total_amount')
        .notEmpty().withMessage('Please enter your total_amount'),
    body('user_email')
        .notEmpty().withMessage('Please enter your email')
        .isEmail().withMessage('Please enter a valid email address')
        .custom(userExists),
];
