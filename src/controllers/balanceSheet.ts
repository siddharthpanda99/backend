import { Request, Response, NextFunction } from "express";
import { User } from "types/User";
import { users } from "fake/Users";
import { fetchCompanySheetSimulated } from "fake/BalanceSheetProvider";

export const getSheetByProvider = async (req: Request, res: Response) => {
    try {
        const provider = req.params.provider;
        const companySheet = await fetchCompanySheetSimulated(provider);
        res.send({ data: companySheet, message: `Got the company sheet from: ${provider}` });
    } catch (error) {
        res.status(500).send({ error: 'Internal Server Error' });
    }
};