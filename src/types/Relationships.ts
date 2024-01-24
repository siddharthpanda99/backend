import { User } from "./User";
import { Room } from "./Room";
import { Hotel } from "./Hotel";
import { Booking } from "./Booking";
import { UserRole } from "./UserRole";

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