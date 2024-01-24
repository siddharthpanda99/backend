import { User } from "types/User";
import { Room } from "types/Room";
import { Hotel } from "types/Hotel";
import { Booking } from "types/Booking";
import { UserRole } from "types/UserRole";

export type UserHotelRelationship = {
    user: User;
    hotels: Hotel[];
}

export type HotelRoomRelationship = {
    hotel: Hotel;
    rooms: Room[];
}

export type UserBookingRelationship = {
    user: User;
    bookings: Booking[];
}


export type RoomBookingRelationship = {
    room: Room;
    bookings: Booking[];
}


export type UserUserRoleRelationship = {
    user: User;
    userRoles: UserRole[];
}