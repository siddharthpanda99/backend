export type User = {
    id: number;
    username: string;
    password: string;
    first_name: string;
    last_name: string;
    email: string;
    token?: string;
    validate: () => any;
}

export type SignUpUserInput = 
    Pick<User, 'username' | 'email' | 'password' | 'first_name' | 'last_name'>;