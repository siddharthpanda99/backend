export type LoanApplication = {
    id: number;
    name: Date;
    provider: Date;
    user_id: number;
    loan_amt: number;
    approved?: number;
    preAssessment?: string
}