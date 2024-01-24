class NotFoundError extends Error {
    message: string;
    readonly statusCode: number;
    readonly errorName: string;
    constructor(message:string) {
        super()
        this.message = message;
        this.statusCode = 404;
        this.errorName = 'NotFoundError'
    }
}

export default NotFoundError;