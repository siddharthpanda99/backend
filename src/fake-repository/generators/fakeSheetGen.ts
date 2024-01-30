export type SheetItem = {
    year: number;
    month: number;
    profitOrLoss: number;
    assetsValue: number;
}

interface GenerateSheetOptions {
    loanAmount: number;
    netPositive: boolean;
    fullAmountEligibility: boolean;
}

export const generateSheet = ({ loanAmount, netPositive, fullAmountEligibility }: GenerateSheetOptions): SheetItem[] => {
    const sheet: SheetItem[] = [];
    let cumulativeAssets = 0;

    for (let month = 12; month >= 1; month--) {
        let profitOrLoss;

        if (netPositive) {
            // Ensure cumulative profitOrLoss is consistently negative
            profitOrLoss = Math.floor(Math.random() * 10000) - (cumulativeAssets + 20000); // Random negative profitOrLoss
        } else {
            profitOrLoss = Math.floor(Math.random() * 20000) - 10000; // Random profitOrLoss, both positive and negative
        }

        const assetsValue = cumulativeAssets + Math.floor(Math.random() * 5000) + 10000; // Random assetsValue, ensuring it's increasing

        cumulativeAssets += assetsValue;

        sheet.push({
            year: 2020,
            month,
            profitOrLoss,
            assetsValue,
        });
    }

    // Ensure the overall profitOrLoss is negative if netPositive is true
    const overallProfitOrLoss = sheet.reduce((total, item) => total + item.profitOrLoss, 0);
    // console.log("🚀 ~ generateSheet ~ overallProfitOrLoss:", overallProfitOrLoss, cumulativeAssets)
    // If we want lossy company
    if (!netPositive) {
        // if overall profit >=0, means profitable company so we mess the last value of sheet to make profitable company lossy
        console.log("Required: Loss ")
        if (overallProfitOrLoss >= 0) {
            // console.log("Got: Loss ", overallProfitOrLoss)
            // Adjust the first entry to make overall profitOrLoss negative
            const adjustment = 2*overallProfitOrLoss;
            // console.log("🚀 ~ generateSheet ~ adjustment:", adjustment, sheet[0].profitOrLoss)
            sheet[0].profitOrLoss -= adjustment;
        } // we do nothing
    } else 
    // If we want profitable
     {
        // console.log("Required: Profit ")
        if (overallProfitOrLoss <= 0) {

            // console.log("Got: Profit ", overallProfitOrLoss)
            // Adjust the first entry to make overall profitOrLoss positive
            const adjustment = 2 * Math.abs(overallProfitOrLoss);

            // console.log("🚀 ~ generateSheet ~ adjustment:", adjustment, sheet[0].profitOrLoss)
            sheet[0].profitOrLoss += adjustment;
        } 
     }

    if (!fullAmountEligibility) {
        // if cumulativeAssets >= loanAmount, means loan 100%
        // console.log("Required: cumulativeAssets Less than loan ", cumulativeAssets, loanAmount)
        if (cumulativeAssets >= loanAmount) {
            // Adjust the first entry to make overall cumulativeAssets less than loanAmount
            const adjustment = 2 * (cumulativeAssets - loanAmount);
            sheet[0].assetsValue -= adjustment;
        } 
        // else we do nothing
    } else
        // Adjust the first entry to make overall cumulativeAssets more than loanAmount
    {
        // console.log("Required: cumulativeAssets more than loan ")
        if (cumulativeAssets < loanAmount) {
            // Adjust the first entry to make overall profitOrLoss positive
            // const adjustment = cumulativeAssets + loanAmount;;
            const adjustment = 2 * (loanAmount - cumulativeAssets);
            sheet[0].assetsValue += adjustment;
        }
    }


     return sheet.reverse()
};


// Example usage with a loan amount of 100,000, ensuring positive profitOrLoss and average assetsValue greater than the loan amount
const loanAmount = 100000;
const generatedSheet1 = generateSheet({ loanAmount, netPositive: true, fullAmountEligibility: true });
const totalAssets1 = generatedSheet1.reduce((total, entry) => total + entry.assetsValue, 0);
const netProfit1 = generatedSheet1.reduce((total, entry) => total + entry.profitOrLoss, 0);

const generatedSheet2 = generateSheet({ loanAmount, netPositive: false, fullAmountEligibility: false });
const totalAssets2 = generatedSheet2.reduce((total, entry) => total + entry.assetsValue, 0);
const netProfit2 = generatedSheet2.reduce((total, entry) => total + entry.profitOrLoss, 0);

console.log( totalAssets1, netProfit1,  totalAssets2, netProfit2);
