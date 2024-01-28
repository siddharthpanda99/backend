Feature: Hotel Booking App Functionality

# Scenario: User Authentication
## User successfully logs into the application
  Given a registered user with username "john_doe" and password "password123"
  When the user logs in with valid credentials
  Then the system should return an authentication token
  And the user should be redirected to the homepage
  And a welcome message should be displayed

## User enters incorrect credentials
  Given a registered user with username "jane_doe" and password "janepassword"
  When the user logs in with invalid credentials
  Then the system should display an error message

# Scenario: Hotel Listing on Homepage
## User sorts hotels by price
  Given the user is on the homepage
  When the user selects to sort hotels by price
  Then the system should display hotels in ascending order of price

## User sorts hotels by rating
  Given the user is on the homepage
  When the user selects to sort hotels by rating
  Then the system should display hotels in descending order of rating

## User searches hotels by name
  Given the user is on the homepage
  When the user enters "Grand Hotel" in the search bar
  Then the system should display only hotels with names containing "Grand Hotel"

## User searches hotels by location
  Given the user is on the homepage
  When the user enters "City Center" in the search bar
  Then the system should display only hotels located in "City Center"

# Scenario: Hotel Details Page
## User views details of a hotel
  Given the user is on the homepage
  When the user clicks on the card for "Luxury Resort"
  Then the system should navigate to the hotel details page
  And the system should display detailed information about "Luxury Resort"

## User views hotel images on details page
  Given the user is on the hotel details page for "Luxury Resort"
  When the system loads hotel details
  Then the system should display actual images of the hotel

## User views hotel description on details page
  Given the user is on the hotel details page for "Luxury Resort"
  When the system loads hotel details
  Then the system should display a detailed description of the hotel

## User views available rooms on details page
  Given the user is on the hotel details page for "Luxury Resort"
  When the system loads hotel details
  Then the system should display a list of available rooms with pricing and amenities

# Scenario: Room Booking
## User selects dates for room booking
  Given the user is on the hotel details page for "Luxury Resort"
  When the user clicks on the "Book Now" button for a specific room
  Then the system should open a popup to choose check-in and check-out dates

## User successfully books a room
  Given the user has chosen check-in on "2024-05-01" and check-out on "2024-05-05"
  When the user submits the room booking form
  Then the system should confirm the booking
  And the booking should appear in the user's bookings list

## User attempts to book an unavailable room
  Given the user has chosen check-in on "2024-06-01" and check-out on "2024-06-05"
  When the user submits the room booking form
  Then the system should display an error indicating the room is not available

# Scenario: View Bookings
## User views their bookings
  Given the user is logged in
  When the user navigates to the bookings tab
  Then the system should display a list of the user's hotel bookings

## User cancels a booking
  Given the user has a confirmed booking for "Luxury Resort"
  When the user clicks on the "Cancel" button for that booking
  Then the system should cancel the booking
  And the booking should no longer appear in the user's bookings list