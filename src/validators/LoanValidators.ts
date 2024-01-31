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

    if (!user) {
        return Promise.reject('The entered user does not exist');
    }

    // If the hotel exists, resolve the promise
    return Promise.resolve();
};

const userHasAleastOneUnApprovedLoan: CustomValidator = async (user_id: number) => {
    // Query the database to check if the hotel with the given ID exists
    const requiredLoanEntries = (LoanAppJson as LoanApplication[]).filter(lapp => {
        return lapp.user_id === user_id && lapp.processingDate && lapp.approved === false
    })

    if (requiredLoanEntries.length>0) {
        return Promise.reject('The user already has applied for a loan that was not approved. You cannot apply for a new loan');
    }

    // If the hotel exists, resolve the promise
    return Promise.resolve();
};

const userAlreadyHasUninitiatedLoanRequest: CustomValidator = async (user_id: number) => {
    // Query the database to check if the hotel with the given ID exists
    const requiredLoanEntries = (LoanAppJson as LoanApplication[]).filter(lapp => {
        // for the user_id, the initiationDate exists, approved is false and processingDate still not present ie still in intiation stage 
        return lapp.user_id === user_id && lapp.initiationDate && !lapp.processingDate && lapp.approved === false
    })

    if (requiredLoanEntries.length > 0) {
        return Promise.reject('The user already has intiated a loan process. Please finalize and submit it before starting a new one');
    }

    // If the hotel exists, resolve the promise
    return Promise.resolve();
};

const userHasNotInitiatedLoanProcess: CustomValidator = async (user_id: number) => {
    if(LoanAppJson.length){
        // Query the datasource to check if the specified user has an existing loan which is not intitiated ie processingDate doesn't exist
        const requiredLoanEntries = LoanAppJson.filter(lapp => {
            return lapp.user_id === user_id && !lapp.processingDate 
        })

        // If there is an existing loan for the user, check if any entry with approved false
        if (requiredLoanEntries.length === 0) {
            //     // Check if any loan intitated but not applied formally
            //     // FOr that, check loan amount, if any entry of requiredLoanEntries has amount = 0, it means, one loan has been initiated but not submitted

            // } else{
            return Promise.reject('The user has not initiated a loan process');
        }

    } else {
        return Promise.reject('There are no entries in the loans application list');
    }

    // If the entry exists, resolve the promise
    return Promise.resolve();
};

export const LoanInitiationValidator = [
    body('user_id')
        .notEmpty().withMessage('Please enter the id for user that is initiating loan process').custom(userExists).custom(userHasAleastOneUnApprovedLoan).custom(userAlreadyHasUninitiatedLoanRequest),
];

export const LoanSubmissionvalidator = [
    body('user_id')
        .notEmpty().withMessage('Please enter the id for user that is submitting loan application').custom(userExists).custom(userHasNotInitiatedLoanProcess).custom(userHasAleastOneUnApprovedLoan),
]
