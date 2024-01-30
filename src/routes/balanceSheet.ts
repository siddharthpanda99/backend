import { Router } from 'express'
import { getSheetByProvider } from 'controllers/balanceSheet';

const balanceSheetRouter = Router();

balanceSheetRouter.route('/balance-sheet/:provider').get(getSheetByProvider);

export default balanceSheetRouter;