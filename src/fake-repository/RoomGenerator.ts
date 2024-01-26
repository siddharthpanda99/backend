// const fs = require('fs');
import fs from 'fs';

import { Room } from "types/Room";
import hotelsJson from "fake/Hotels.json";
import { amenitiesList } from 'fake/Amenities';

function getRandomAmenities(amenitiesList: any) {
    const maxAmenities = 5;
    const numberOfAmenities = Math.floor(Math.random() * (maxAmenities + 1));

    // Shuffle the amenities list to get random selection
    const shuffledAmenities = amenitiesList.sort(() => Math.random() - 0.5);

    // Slice the shuffled array to get a random selection of amenities
    const selectedAmenities = shuffledAmenities.slice(0, numberOfAmenities);

    return selectedAmenities;
}

// Function to generate rooms for a hotel with different types
const generateRoomsForHotel = (hotelId: number): Room[] => {
  const roomTypes = ['economy', 'business', 'premium', 'luxury'];

  return roomTypes.map((type, index) => ({
    id: index + 1,
    type,
    noOfRooms: Math.ceil(Math.random() * 5),
    price: Math.floor(Math.random() * 200) + 100, // Random price between 100 and 300
      amenities: [...amenitiesList.slice(0, 5), ...getRandomAmenities(amenitiesList.slice(5))], // Sample amenities
    hotel_id: hotelId,
  }));
};

// Generating rooms for each hotel
const hotelsWithRooms: Record<string, Room[]> = {};

// Assume you already have an array of hotels named 'hotels'
const hotelIds = hotelsJson.map((hotel) => hotel.id);

// Generating rooms for each hotel
hotelIds.forEach((hotelId) => {
  console.log("🚀 ~ hotelIds.forEach ~ hotelId:", hotelId)
  hotelsWithRooms[parseInt(hotelId)] = generateRoomsForHotel(hotelId);
  if(hotelsJson[hotelId]){hotelsJson[hotelId]['price'] = generateRoomsForHotel(hotelId)[0].price;}
  console.log("🚀 ~ hotelIds.forEach ~ generateRoomsForHotel(hotelId):", generateRoomsForHotel(hotelId)[0].price, hotelsJson[hotelId])
});
console.log(hotelsJson)

// Creating a JSON file
fs.writeFileSync('src/fake-repository/hotelsWithRooms.json', JSON.stringify(hotelsWithRooms, null, 2));
fs.writeFileSync('src/fake-repository/Hotels.json', JSON.stringify(hotelsJson, null, 2));

console.log('JSON file generated: hotelsWithRooms.json');