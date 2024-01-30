import { Request, Response, NextFunction } from "express";
import fs from 'fs';
import { fetchCompanySheetSimulated } from "fake/BalanceSheetProvider";
import { LoanApplication } from "types/LoanApplication";
import { fetchDecision } from "fake/engine/decision";
import { message } from 'antd';

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

// Submit app with bal sheet
export const submitApp = async (req: Request, res: Response) => {
    try {
        const body: LoanApplication = req.body;
        console.log("🚀 ~ submitApp ~ body:", body)
        // For now, we don't allow modifications to company sheets
        // Check for conditions and send request to decision engine
        const decisionENgineRes = await fetchDecision(body)
        console.log("🚀 ~ submitApp ~ decisionENgineRes:", decisionENgineRes)
        res.status(200).send({ data: decisionENgineRes, message: "Your loan request is submitted successfully" });
        
    } catch (error) {
        res.status(500).send({ error: 'Internal Server Error' });
    }
};