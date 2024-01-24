class BadRequestError extends Error {
    message: string;
    readonly statusCode: number;
    readonly errorName: string;
    constructor(message: string) {
        super()
        this.message = message;
        this.statusCode = 400;
        this.errorName = 'BadRequestError'
    }
}

export default BadRequestError;