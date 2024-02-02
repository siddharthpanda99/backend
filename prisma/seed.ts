//TO seed data, run 
// npx prisma db seed 

import { PrismaClient } from '@prisma/client'
import hotelsJson from 'fake/Hotels.json';
import {users} from 'fake/Users'
import { User } from '../src/types/User';

const prisma = new PrismaClient()
console.log(hotelsJson)
console.log("🚀 ~ users:", users)


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

const seedUsers = (datasource) => {
    // adding continents to the data
    Promise.all(
        datasource.map(async data => {
            const { username, password, first_name, last_name, email } = data;
            const response = await prisma.user.create({
                data: {
                    first_name, 
                    last_name, 
                    username, 
                    password, 
                    email, 
                    createdAt: new Date(), 
                    updatedAt: new Date()
                }
            })
            return response;
        })
    );
};

seedHotels(hotelsJson)
seedUsers(users)
