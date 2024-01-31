import balMyobJson from 'fake/loan/Bal_sheet_myob.json'
import { LoanApplication } from 'types/LoanApplication';

const decisionEngine = (details: LoanApplication) => {
    const netProfit = balMyobJson?.reduce((total, item) => total + item.profitOrLoss, 0)
    console.log("🚀 ~ decisionEngine ~ netProfit:", netProfit)
    const avgAssetVal = balMyobJson.reduce((total, item) => total + item.assetsValue, 0)
    console.log("🚀 ~ decisionEngine ~ avgAssetVal:", avgAssetVal)
    let res;
    if(netProfit > 0) {
        res =  {...details, "preAssessment": "60", approved: true }
    } else res = { ...details, "preAssessment": "20", approved: true }
    if (avgAssetVal > details.loan_amt) {
        res = { ...details, "preAssessment": "100", approved: true }
    } else res = { ...details, "preAssessment": "20", approved: true }
    if (netProfit < 0 && avgAssetVal < details.loan_amt) {
        res = { ...details, "preAssessment": "0", approved: false }
    }
    return res
}

export const fetchDecision = (body: LoanApplication) => {
    return new Promise((resolve) => {
        setTimeout(() => {
            const data = decisionEngine(body)
            resolve(data)
        }, 2000); // 2-second delay
    });
};