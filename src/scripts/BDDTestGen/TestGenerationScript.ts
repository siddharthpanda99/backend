import fs from 'fs';
import path from 'path'; // Import path module for path operations
import { defineFeature, loadFeature } from 'jest-cucumber';

// Assuming the script is in the same directory as the Gherkin feature file
const scriptDirectory = path.dirname(process.argv[1]);
console.log("🚀 ~ scriptDirectory:", scriptDirectory)
const featureFilePath = path.join(scriptDirectory, 'HotelBooking.feature');

// Check if the feature file exists
if (!fs.existsSync(featureFilePath)) {
    throw new Error(`Feature file not found: ${featureFilePath}`);
}

// Read the content of the Gherkin feature file
const featureFileContent = fs.readFileSync(featureFilePath, 'utf-8');

// Load the Gherkin feature
const feature = loadFeature(featureFileContent);

// Create an array to store the test script lines
const testScriptLines: string[] = [];

// Define Jest features based on Gherkin feature
testScriptLines.push(`
import { test, expect } from '@playwright/test';

const feature = loadFeature(${JSON.stringify(featureFileContent)});

defineFeature(feature, (test) => {
  // Implement any setup steps if needed
`);

// Iterate through Gherkin scenarios
feature.scenarios.forEach((scenario) => {
    // Add a test block for each scenario
    testScriptLines.push(`  
  // Scenario: ${scenario.title}
  test('${scenario.title}', async ({ given, when, then }) => {`);

    // Iterate through Gherkin steps of the scenario
    scenario.steps.forEach((step) => {
        const stepText = step.stepText;
        switch (step.keyword.toLowerCase()) {
            case 'given':
                testScriptLines.push(`    given('${stepText}');`);
                break;
            case 'when':
                testScriptLines.push(`    when('${stepText}');`);
                break;
            case 'then':
                testScriptLines.push(`    then('${stepText}');`);
                break;
            default:
                throw new Error(`Unsupported step keyword: ${step.keyword}`);
        }
    });

    // Close the test block for the scenario
    testScriptLines.push(`  });`);
});

// Close the Jest feature definition
testScriptLines.push(`});`);

// Write the test script to a file named 'all.test.ts'
fs.writeFileSync('all.test.ts', testScriptLines.join('\n'), 'utf-8');

console.log('Test script generated successfully: all.test.ts');
