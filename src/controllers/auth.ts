import { Request, Response, NextFunction } from "express";
import { SignUpUserInput, User } from "types/User";
import { users } from "fake/Users";

/**
 * Handles user registration.
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
 * This function is responsible for handling user registration requests. It validates
 * the provided user data and responds accordingly.
 *
 * @example
 * // Sample request body:
 * // {
 * //   "email": "user@example.com",
 * //   "password": "password123"
 * // }
 *
 * // Successful response:
 * // {
 * //   "data": {
 * //     "email": "user@example.com",
 * //     "password": "password123"
 * //   },
 * //   "message": "User signed up successfully"
 * // }
 *
 * // Failed response:
 * // {
 * //   "message": "Please enter username and/or password"
 * // }
 */
const signUpUser = (req: Request, res: Response) => {
    const body: SignUpUserInput = req.body;
    if (!body.email || !body.password) {
        res.status(403).send({ data: {}, message: 'Please enter username and/or password' })
    }
    else res.status(200).send({ data: body, message: 'User signed up successfully' })
}

/*****************************************************************************************************************************************************/
/*****************************************************************************************************************************************************/

/**
 * Handles user login.
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
 * This function is responsible for handling user login requests. It checks the provided
 * credentials against the stored user data and responds accordingly.
 *
 * @example
 * // Sample request body:
 * // {
 * //   "email": "user@example.com",
 * //   "password": "password123"
 * // }
 *
 * // Successful response:
 * // {
 * //   "data": {
 * //     "email": "user@example.com",
 * //     "token": "generatedToken123"
 * //   },
 * //   "message": "User logged in successfully"
 * // }
 *
 * // Failed response:
 * // {
 * //   "message": "Check email/password"
 * // }
 */
const loginUser = (req: Request, res: Response) => {
    const body: User = req.body;
    // if (!body.email || !body.password) {
    //     res.status(403).send({ data: {}, message: 'Please enter username and/or password' })
    // } else {

    const req_user: User | undefined = users.find(user => user.email === body.email && user.password === body.password)
    if (req_user) {
        const { email, token, id } = req_user;
        res.status(200).send({ data: { email, token, id }, message: 'User logged in successfully' })
    } else {
        res.status(200).send({ data: [], message: 'Check email/password' })
    }
}
// }

export { signUpUser, loginUser };