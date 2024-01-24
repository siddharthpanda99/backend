

class UnAuthorizedError extends Error {
    message: string;
    readonly statusCode: number;
    readonly errorName: string;
    constructor(message: string) {
        super()
        this.message = message;
        this.statusCode = 401;
        this.errorName = 'UnAuthorizedError'
    }
}

export default UnAuthorizedError;