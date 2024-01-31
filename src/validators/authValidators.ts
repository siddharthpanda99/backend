import { body } from 'express-validator';

export const loginUserValidation = [
    body('email')
        .notEmpty().withMessage('Please enter your email')
        .isEmail().withMessage('Please enter a valid email address'),
    body('password')
        .notEmpty().withMessage('Please enter your password'),
];
