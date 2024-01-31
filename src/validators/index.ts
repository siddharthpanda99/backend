import { Request, Response, NextFunction } from 'express';
import { validationResult } from 'express-validator';
import { loginUserValidation } from 'validators/authValidators';
import { UserBookingValidation } from 'validators/UserHotelValidators';

const allValidatorsPassed = (req: Request, res: Response, next: NextFunction) => {
    const errors = validationResult(req);

    if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
    }

    // If there are no validation errors, proceed to the next middleware (i.e., the controller)
    next();
};

export { loginUserValidation, UserBookingValidation, allValidatorsPassed };
