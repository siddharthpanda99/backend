import { Router } from 'express'
import { getSheetByProvider, submitApp } from 'controllers/loan';

const loanRouter = Router();

loanRouter.route('/loan/bal-sheet/:provider').get(getSheetByProvider);
loanRouter.route('/loan/submit').post(submitApp);

export default loanRouter;