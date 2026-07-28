const puppeteer = require('puppeteer');
const fs = require('fs');

async function captureScreenshot(url, outputPath) {
    console.log(`Starting headless browser to capture: ${url}`);
    
    // Launch browser
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    const page = await browser.newPage();
    
    // Set standard viewport for visual QC
    await page.setViewport({ width: 1280, height: 800 });
    
    try {
        console.log('Navigating to page...');
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
        
        console.log(`Taking screenshot... saving to ${outputPath}`);
        await page.screenshot({ path: outputPath, fullPage: true });
        
        console.log('Visual QC capture complete!');
    } catch (error) {
        console.error('Failed to capture screenshot:', error.message);
    } finally {
        await browser.close();
    }
}

// Simple CLI logic
const args = process.argv.slice(2);
if (args.length < 2) {
    console.log('Usage: node screenshot-preview.js <URL> <output-file.png>');
    process.exit(1);
}

const targetUrl = args[0];
const outFile = args[1];

captureScreenshot(targetUrl, outFile);
