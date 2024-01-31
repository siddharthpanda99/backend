import balMyobJson from 'fake/loan/Bal_sheet_myob.json'
import { LoanApplication } from 'types/LoanApplication';

const decisionEngine = (details: LoanApplication) => {
    const netProfit = balMyobJson?.reduce((total, item) => total + item.profitOrLoss, 0)
    console.log("🚀 ~ decisionEngine ~ netProfit:", netProfit)
    const avgAssetVal = balMyobJson.reduce((total, item) => total + item.assetsValue, 0)
    console.log("🚀 ~ decisionEngine ~ avgAssetVal:", avgAssetVal)
    let res = { ...details, "preAssessment": "60", approved: true, processingDate: (new Date()).toString() }
    if(netProfit > 0) {
        res =  res
    } else res = { ...res, "preAssessment": "20" }
    if (avgAssetVal > details.loan_amt) {
        res = { ...res, "preAssessment": "100"}
    } else res = { ...res, "preAssessment": "20" }
    if (netProfit < 0 && avgAssetVal < details.loan_amt) {
        res = { ...res, "preAssessment": "0", approved: false }
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