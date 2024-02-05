export type LoanApplication = {
    id?: number;
    companyName: string;
    provider: string;
    user_id: number;
    loan_amt: number;
    approved?: boolean;
    initiationDate: string;
    processingDate: string;
    preAssessment?: string
}

export type LoanInitiationInput = {
    user_id: number;
}