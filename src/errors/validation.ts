class ValidationError extends Error {
    message: string;
    fieldName: string;
    readonly statusCode: number;
    readonly errorName: string;
    constructor(message: string, fieldName: string) {
        super();
        this.message = message;
        this.statusCode = 400;
        this.errorName = 'ValidationError';
        this.fieldName = fieldName;
    }
}

export default ValidationError;