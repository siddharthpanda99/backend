import { hotels } from "fake/Hotels";
import roomsJson from 'fake/hotelsWithRooms.json'

export const getHotelDetailsById = (hotelId: string) => {
    const hotel = hotels.find(hotel => {
        return hotel.id === parseInt(hotelId)
    })

    let hotelDetail;
    if (!hotel) {
        hotelDetail = "No hotel found for the specified id"
    } else {
        const rooms = roomsJson[hotelId]
        console.log("🚀 ~ getHotelById ~ rooms:", rooms)
        hotel['rooms'] = rooms
        hotelDetail = hotel
    }
    return hotelDetail
}
