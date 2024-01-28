import { Room } from "./Room";

export type Hotel = {
    id: number;
    name: string;
    location: string;
    rating: number;
    price: number;
    rooms: Room[];
}
