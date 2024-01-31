import { CustomValidator, body } from 'express-validator';
import LoanAppJson from 'fake/LoanApplications.json'
import { users } from 'fake/Users';
import { LoanApplication } from 'types/LoanApplication';
import { User } from 'types/User';

const userExists: CustomValidator = async (user_id: number) => {
    // Query the database to check if the hotel with the given ID exists
    const user: User | undefined = users.find(usr => {
        return usr.id === user_id
    })
    console.log("🚀 ~ constuserExists:CustomValidator= ~ user:", user)

    if (!user) {
        return Promise.reject('The entered user does not exist');
    }

    // If the hotel exists, resolve the promise
    return Promise.resolve();
};

const userAlreadyAppliedForOneLoan: CustomValidator = async (user_id: number) => {
    // Query the database to check if the hotel with the given ID exists
    const user: User | undefined = LoanAppJson.find(lapp => {
        return lapp.user_id === user_id
    })

    if (user) {
        return Promise.reject('The user already has applied for a loan');
    }

    // If the hotel exists, resolve the promise
    return Promise.resolve();
};

const userHasAleastOneUnApprovedLoan: CustomValidator = async (user_id: number) => {
    // Query the database to check if the hotel with the given ID exists
    const loaningUser = LoanAppJson.find(lapp => {
        return lapp.user_id === user_id && lapp.approved === false
    })

    if (loaningUser) {
        return Promise.reject('The user already has applied for a loan that was not approved. You cannot apply for a new loan');
    }

    // If the hotel exists, resolve the promise
    return Promise.resolve();
};

export const LoanInitiationValidator = [
    body('user_id')
        .notEmpty().withMessage('Please enter the id for user you are booking for').custom(userExists).custom(userHasAleastOneUnApprovedLoan),
];
