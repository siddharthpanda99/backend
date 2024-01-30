import { generateSheet } from "./generators/fakeSheetGen";
import { SheetItem } from "./generators/fakeSheetGen";

const XeroSheet: SheetItem[] = generateSheet({loanAmount: 100000, netPositive: true, fullAmountEligibility: true})

// Note that MYOBSheet has been chosen in such a way that it 
const MYOBSheet: SheetItem[] = generateSheet({ loanAmount: 100000, netPositive: false, fullAmountEligibility: false })


export const fetchCompanySheetSimulated = (source: string) => {
    return new Promise((resolve) => {
        setTimeout(() => {
            const data = source === 'XERO' ? XeroSheet : MYOBSheet
            resolve(data)
        }, 2000); // 2-second delay
    });
};

// fetchCompanySheetSimulated("XERO").then((data: SheetItem[]) => console.log(data, data.reduce((total, entry) => total + entry.assetsValue, 0), data.reduce((total, entry) => total + entry.profitOrLoss, 0)))