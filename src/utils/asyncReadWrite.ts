import * as fs from 'fs/promises';

export const readJsonFileAsync = async (filePath: string): Promise<any> => {
    try {
        const fileContent = await fs.readFile(filePath, 'utf-8');
        return JSON.parse(fileContent);
    } catch (error) {
        const typedError = error as Error; 
        console.error(`Error reading JSON file ${filePath}: ${typedError.message}`);
        throw error;
    }
};

export const writeJsonFileAsync = async (filePath: string, data: any): Promise<void> => {
    try {
        const jsonData = JSON.stringify(data, null, 2);
        await fs.writeFile(filePath, jsonData, 'utf-8');
    } catch (error) {
        const typedError = error as Error; 
        console.error(`Error writing JSON file ${filePath}: ${typedError.message}`);
        throw error;
    }
};
