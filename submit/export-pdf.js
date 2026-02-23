#!/usr/bin/env node
/**
 * Export slide-deck.html to PDF using Puppeteer
 *
 * Usage:
 *   npx puppeteer browsers install chrome
 *   node export-pdf.js
 *
 * Or with bunx:
 *   bunx puppeteer browsers install chrome
 *   bun export-pdf.js
 */

const puppeteer = require('puppeteer');
const path = require('path');

async function exportToPDF() {
  const browser = await puppeteer.launch();
  const page = await browser.newPage();

  // Set viewport to slide dimensions
  await page.setViewport({ width: 1024, height: 576 });

  // Load the HTML file
  const htmlPath = path.join(__dirname, 'slide-deck.html');
  await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle0' });

  // Export to PDF with links preserved
  await page.pdf({
    path: 'slide-deck.pdf',
    width: '1024px',
    height: '576px',
    printBackground: true,
    preferCSSPageSize: true,
    tagged: true,
  });

  console.log('PDF exported: slide-deck.pdf');
  await browser.close();
}

exportToPDF().catch(console.error);
