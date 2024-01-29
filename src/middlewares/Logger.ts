
import expressWinston from 'express-winston'
import { transports, format } from "winston";
// import winstonMongodb from 'winston-mongodb'

export const Logger = expressWinston.logger({
    transports: [
        new transports.Console({ level: 'warn' }),
        // new transports.File({
        //     level: 'warn',
        //     filename: 'warningLogs.log'
        // }),
        // new transports.MongoDB({
        //     db: 'your_db_uri',
        // })
    ],
    format: format.combine(
        format.json(),
        format.timestamp(),
        format.prettyPrint()
    ),
    statusLevels: true
})