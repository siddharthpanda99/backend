import { UserHotelRoomBooking } from "types/RoomBooking"

export const isUniqueBooking = (BookingsList: UserHotelRoomBooking[], body: UserHotelRoomBooking) => {
    const matchingBookings = BookingsList.filter((booking: UserHotelRoomBooking) => booking.room_id === body.room_id && booking.user_id === body.user_id && booking.hotel_id === body.hotel_id && dateRangeOverlap(booking, body)).length;
    // In case these matched, check for dates, they shouldn't overlap
    // if they overlap


    console.log("🚀 ~ isUniqueBooking ~ matchingBookings:", matchingBookings)
    return matchingBookings === 0
}

const dateRangeOverlap = (booking1, booking2) => {
        const start1 = new Date(booking1.check_in_date)
        const end1 = new Date(booking1.check_out_date)
        const start2 = new Date(booking2.check_in_date)
        const end2 = new Date(booking2.check_out_date)
    return start1 <= end2 && end1 >= start2
}