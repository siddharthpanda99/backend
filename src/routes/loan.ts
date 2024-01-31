import { Router } from 'express'
import { getSheetByProvider, initiateLoanApp, submitApp } from 'controllers/loan';
import { LoanInitiationValidator } from 'validators/LoanValidators';
import { allValidatorsPassed } from 'validators/index';

const loanRouter = Router();
// This is the first step for user to initiate a loan, when this api is called, it creates a LoanApplicationObject in the backend with the necessary fields set as empty, only user_id field is populated as the loggedIn user
loanRouter.route('/loan/initiate').post(LoanInitiationValidator, allValidatorsPassed, initiateLoanApp);

// Request balance sheet during the review process, the UI will see the doc and make changes if needed
loanRouter.route('/loan/bal-sheet/:provider').get(getSheetByProvider)

// When loan app submitted, we receive the balance sheet + user + comapny details, then we send out the request to decision engine that will process the whole info and return the response back to user that loan process in progress
loanRouter.route('/loan/submit').post(submitApp);

export default loanRouter;