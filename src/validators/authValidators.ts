import { Request, Response, NextFunction } from 'express';
import { body, validationResult } from 'express-validator';

const loginUserValidation = [
    body('email')
        .notEmpty().withMessage('Please enter your email')
        .isEmail().withMessage('Please enter a valid email address'),
    body('password')
        .notEmpty().withMessage('Please enter your password'),
];

const allValidatorsPassed = (req: Request, res: Response, next: NextFunction) => {
    const errors = validationResult(req);

    if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
    }

    // If there are no validation errors, proceed to the next middleware (i.e., the controller)
    next();
};

export { loginUserValidation, allValidatorsPassed };
