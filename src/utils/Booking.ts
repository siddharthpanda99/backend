import { UserHotelRoomBooking, UserHotelRoomBookingDetails } from "types/RoomBooking"
import { Hotel } from "types/Hotel";
import { Booking } from "types/Booking";
import { Room } from "types/Room";

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

export function populateBookingsWithDetails(hotels: Hotel[], rooms: Record<number, Room[]>, bookings: UserHotelRoomBooking[]) {
    const bookingArray: UserHotelRoomBookingDetails[] = [];

    bookings.forEach(booking => {
        const hotel = hotels.find(h => h.id === booking.hotel_id);
        const room = rooms[booking.hotel_id]?.find(r => r.id === booking.room_id);

        if (hotel && room) {
            const bookingDetails = {
                booking_id: booking.booking_id,
                user_email: booking.user_email,
                check_in_date: booking.check_in_date,
                check_out_date: booking.check_out_date,
                hotel_name: hotel.name,
                room_details: {
                    type: room.type,
                    noOfRooms: room.noOfRooms,
                    amenities: room.amenities,
                },
                total_amount: room.price,
            };

            bookingArray.push(bookingDetails);
        }
    });

    return bookingArray;
}