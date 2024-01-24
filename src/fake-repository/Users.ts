import { User } from "../types/User";
export const users: User[] = [
    {
        id: 1,
        username: 'john_doe',
        password: 'password123',
        first_name: 'John',
        last_name: 'Doe',
        email: 'john@example.com',
        validate: () => console.log('Validation function for John Doe'),
    },
    {
        id: 2,
        username: 'jane_doe',
        password: 'securepass',
        first_name: 'Jane',
        last_name: 'Doe',
        email: 'jane@example.com',
        validate: () => console.log('Validation function for Jane Doe'),
    },
    {
        id: 3,
        username: 'bob_smith',
        password: '123456',
        first_name: 'Bob',
        last_name: 'Smith',
        email: 'bob@example.com',
        validate: () => console.log('Validation function for Bob Smith'),
    },
];