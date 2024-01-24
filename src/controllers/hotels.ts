import { Request, Response, NextFunction } from "express";
import { hotels } from "fake/Hotels";

const getListOfHotels = (req: Request, res: Response) => {
    res.send({ hotels, message: 'Fetched a list of hotels' })
}

const getHotelById = (req: Request, res: Response) => {
    const hotelId = req.params.hotelId;
    res.send({ message: `Fetched hotel by id: ${hotelId}` })
}

const bookHotel = (req: Request, res: Response) => {
    const body = req.body;
    console.log("🚀 ~ bookHotel ~ body:", body)
    res.send({message: body})
}

const checkBookingStatus = (req: Request, res: Response) => {
    const bookingId = req.params.bookingId;
    console.log("🚀 ~ bookHotel ~ body:", bookingId)
    res.send({ message: bookingId })
}
export { getListOfHotels, getHotelById, bookHotel, checkBookingStatus };