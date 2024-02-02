import { PrismaClient } from '@prisma/client'
import hotelsJson from 'fake/Hotels.json';

const prisma = new PrismaClient()
console.log(hotelsJson)

// hotelsJson.map

const seedHotels = (datasource) => {
    // adding continents to the data
    Promise.all(
        datasource.map(async hotel => {
            const { name, location, price, rating } = hotel;
            const response = await prisma.hotel.create({data: {
                name, location, price, rating 
            }})
            return response;
        })
    );
};

seedHotels(hotelsJson)
