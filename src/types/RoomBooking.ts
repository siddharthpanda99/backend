export type RoomBooking = {
  id: number;
  booking_id: number;
  room_id: number;
  check_in_date: Date;
  check_out_date: Date;
  total_amount: number;
}