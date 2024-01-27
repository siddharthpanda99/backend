import { UserHotelRoomBooking } from "types/RoomBooking"

export const isUniqueBooking = (BookingsList: UserHotelRoomBooking[], body: UserHotelRoomBooking) => {
    const matchingBookings = BookingsList.filter((booking: UserHotelRoomBooking) => booking.room_id === body.room_id && booking.user_email === body.user_email && booking.hotel_id === body.hotel_id).length;
    // In case these matched, check for dates, they shouldn't overlap
    // if they overlap
    return matchingBookings === 0
}

const dateRangeOverlap = (booking1: UserHotelRoomBooking, booking2: UserHotelRoomBooking) => {
        const start1 = new Date(booking1.check_in_date)
        const end1 = new Date(booking1.check_out_date)
        const start2 = new Date(booking2.check_in_date)
        const end2 = new Date(booking2.check_out_date)
    return start1 <= end2 && end1 >= start2
}

export const areDatesAlreadyBlocked = (BookingsList: UserHotelRoomBooking[], body: UserHotelRoomBooking) => {
    const matchingBookings = BookingsList.filter((booking: UserHotelRoomBooking) => booking.room_id === body.room_id && booking.hotel_id === body.hotel_id && dateRangeOverlap(booking, body)).length;
    console.log("🚀 ~ areDatesAlreadyBlocked****************************************** ~ matchingBookings:", matchingBookings)
    // if there is a matching booking, return false
    return matchingBookings 
}