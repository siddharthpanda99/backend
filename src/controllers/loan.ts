import { Request, Response, NextFunction } from "express";
import fs from 'fs';
import { fetchCompanySheetSimulated } from "fake/BalanceSheetProvider";
import { LoanApplication } from "types/LoanApplication";
import { fetchDecision } from "fake/engine/decision";

// During intiation, call this api to create a local file
// You hit it only once during the loan process init and get back relevant data for all possible providers
export const getSheetByProvider = async (req: Request, res: Response) => {
    try {
        const provider = req.params.provider;
        const companySheet = await fetchCompanySheetSimulated(provider);
        fs.writeFileSync(`src/fake-repository/loan/Bal_sheet_${provider}.json`, JSON.stringify(companySheet, null, 2));
        res.send({ data: companySheet, message: `Got the company sheet from$$$$: ${provider}` });
    } catch (error) {
        res.status(500).send({ error: 'Internal Server Error' });
    }
};

// Call this to get company datasheet for review
export const requestBalSheet = async (req: Request, res: Response) => {
    try {
        const provider = req.params.provider;
        const companySheet = fs.readFileSync(`src/fake-repository/loan/Bal_sheet_${provider}.json`);
        res.send({ data: companySheet, message: `Got the company sheet from: ${provider}` });
    } catch (error) {
        res.status(500).send({ error: 'Internal Server Error' });
    }
};

// Initiate Loan application payload: username, comapnyname, 
export const initiateLoanApp = async (req: Request, res: Response) => {
    try {
        const body: LoanApplication = req.body;
        const fileBuffer = fs.readFileSync('src/fake-repository/LoanApplications.json').toString();
        const LoansList = JSON.parse(fileBuffer);
        const loanObj = {
            id: 0,
            companyName: '',
            provider: '',
            user_id: 0,
            loan_amt: 0,
            approved: false,
            preAssessment: "",
            processingDate: "",
            initiationDate: (new Date()).toString()
        }
        if (LoansList.length) {
            // Means there are some loans already there
            // pick the last element
            const lastId = LoansList[LoansList.length - 1]["id"];
            LoansList.push({
                ...loanObj,
                id: lastId+1,
                user_id: body.user_id
            })
        } else LoansList.push({
            ...loanObj,
            id: 1,
            user_id: body.user_id
        })
        fs.writeFileSync('src/fake-repository/LoanApplications.json', JSON.stringify(LoansList, null, 2));
        console.log("🚀 ~ initiateLoanApp ~ LoansList:", LoansList)
        res.status(200).send({ message: "Your loan request is submitted successfully" });

    } catch (error) {
        res.status(500).send({ error: 'Internal Server Error' });
    }
};


// Submit app with bal sheet
export const submitApp = async (req: Request, res: Response) => {
    try {
        const body: LoanApplication = req.body;
        console.log("🚀 ~ submitApp ~ body:", body)
        // For now, we don't allow modifications to company sheets
        // Check for conditions and send request to decision engines
        const decisionENgineRes: LoanApplication | any = await fetchDecision(body)
        console.log("🚀 ~ submitApp ~ decisionENgineRes:", decisionENgineRes)

        // Read from the loanslist to fin the requiredLoad entry we want to modify
        const fileBuffer = fs.readFileSync('src/fake-repository/LoanApplications.json').toString();
        const LoansList = JSON.parse(fileBuffer);
        const reqLoanId = LoansList.findIndex((el: LoanApplication) =>  el.user_id == body.user_id)

        // Update the required loan entry by populating with data from decisionENgineRes
        LoansList[reqLoanId] = { ...LoansList[reqLoanId], companyName: body.companyName, provider: body.provider, loan_amt: body.loan_amt, preAssessment: decisionENgineRes.preAssessment, processingDate: decisionENgineRes.processingDate }
        fs.writeFileSync('src/fake-repository/LoanApplications.json', JSON.stringify(LoansList, null, 2));
        res.status(200).send({ data: decisionENgineRes, message: "Your loan request is submitted successfully" });
        
    } catch (error) {
        res.status(500).send({ error: 'Internal Server Error' });
    }
};