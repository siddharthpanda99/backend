export type UserHotelRoomBooking = {
  booking_id: number;
  room_id: number;
  check_in_date: string;
  check_out_date: string;
  total_amount: number;
  user_email: string;
  hotel_id: number;
}

export type UserHotelRoomBookingDetails = {
      booking_id: number;
      user_email: string;
      check_in_date: string;
      check_out_date: string;
      hotel_name: string;
      room_details: {
        type: string;
        noOfRooms: number;
        amenities: string[];
      },
      total_amount: number;
    }