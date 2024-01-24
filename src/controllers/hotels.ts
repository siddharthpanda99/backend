import { Request, Response, NextFunction } from "express";

const getListOfHotels = (req: Request, res: Response) => {
    res.send({ message: 'Fetched a list of hotels' })
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

export { getListOfHotels, getHotelById, bookHotel };