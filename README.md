
# Nodejs + Express

# Hotel Booking app

## Overview

Brief description of your project.

## Features

### 1. Login

- Login api returns a token
- URL: http://localhost:8000/api/v1/login
- Payload `{
  "email": "john@example.com",
  "password": "password123"
}`
- Response: `{
  "data": {
    "email": "john@example.com",
    "token": "Mo+/skPN9xxQUQ2BNUPt5Z0KlJ+69L4X"
  },
  "message": "User logged in successfully"
}`
- Token used for subsequest request

### 2. Hotel List


- a Hotel List API with search, sort and filter options on server side
  Eg: http://localhost:8000/api/v1/hotels?sortField=rating&sortOrder=descsortField=price&sortOrder=desc&filters[location]=Countryside&filters[location]=Countryside&filters[location]=Downtown

### 3. Hotel Details api GET

- URL: http://localhost:8000/api/v1/hotels/1 
- Response: ```yaml
{
  "data": {
    "id": 1,
    "name": "Luxury Palace Hotel",
    "location": "City Center",
    "price": 100,
    "rating": 3.7,
    "rooms": [
      {
        "id": 1,
        "type": "economy",
        "noOfRooms": 2,
        "price": 168,
        "amenities": [
          "Free Wi-Fi",
          "Complimentary Breakfast",
          "Room Service",
          "Free Parking",
          "On-site Restaurant",
          "Pet-Friendly"
        ],
        "hotel_id": 1
      },
      {
        "id": 2,
        "type": "business",
        "noOfRooms": 2,
        "price": 143,
        "amenities": [
          "Free Wi-Fi",
          "Complimentary Breakfast",
          "Room Service",
          "Free Parking",
          "On-site Restaurant",
          "Childcare Services",
          "Concierge Service"
        ],
        "hotel_id": 1
      },
      {
        "id": 3,
        "type": "premium",
        "noOfRooms": 3,
        "price": 149,
        "amenities": [
          "Free Wi-Fi",
          "Complimentary Breakfast",
          "Room Service",
          "Free Parking",
          "On-site Restaurant",
          "Spa and Wellness Center",
          "Fitness Center",
          "Laundry Service",
          "24-Hour Front Desk"
        ],
        "hotel_id": 1
      },
      {
        "id": 4,
        "type": "luxury",
        "noOfRooms": 5,
        "price": 274,
        "amenities": [
          "Free Wi-Fi",
          "Complimentary Breakfast",
          "Room Service",
          "Free Parking",
          "On-site Restaurant",
          "Lounge/Bar Area",
          "Meeting Facilities",
          "Pet-Friendly"
        ],
        "hotel_id": 1
      }
    ]
  },
  "message": "Fetched hotel by id: 1"
}
```

### 4. Room Booking

- Clicking on a room card opens a popup to choose check-in and check-out dates.
- Submitting the form books the room.
- Checks room availability and throws an error if the room is not available.

### 5. View Bookings

- Access a list of your hotel bookings in the bookings tab.



## Technologies Used

    - Typescript
    - Tailwind
    - react-material-ui


## Setup

Install Nodejs and pnpm in your system

## Usage

To run locally, clone this repo, navigate to it's root and type the following
pnpm i
pnpm run dev

## Running on Docker
- docker build -t frontend .
- docker run -p 5173:5173 frontend

## Contributing

Provide guidelines for contributing to your project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


## Acknowledgments

Give credit to any resources or inspirations you used in your project.




