import hotels from "fake/Hotels.json";
import roomsJson from 'fake/hotelsWithRooms.json'
import { Hotel } from "types/Hotel";

export const getHotelDetailsById = (hotelId: string) => {
    const hotel: Hotel|undefined = hotels.find(hotel => {
        return hotel.id === parseInt(hotelId)
    })
    const roomsData:any = roomsJson;

    let hotelDetail;
    if (!hotel) {
        hotelDetail = "No hotel found for the specified id"
    } else {
        const rooms = roomsData[hotelId]
        // console.log("🚀 ~ getHotelById ~ rooms:", rooms)
        hotel['rooms'] = rooms
        hotelDetail = hotel
    }
    return hotelDetail
}
