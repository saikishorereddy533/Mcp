const axios = require("axios");
const ExcelJS = require("exceljs");
const fs = require("fs");
const path = require("path");

/**
 * Recursively flattens a nested object using dot notation
 * Example: { a: { b: 1 } } -> { "a.b": 1 }
 */
function flattenObject(obj, parentKey = "", res = {}) {
  for (let key in obj) {
    if (!obj.hasOwnProperty(key)) continue;
    const newKey = parentKey ? `${parentKey}.${key}` : key;

    if (typeof obj[key] === "object" && obj[key] !== null && !Array.isArray(obj[key])) {
      flattenObject(obj[key], newKey, res);
    } else {
      res[newKey] = Array.isArray(obj[key]) ? JSON.stringify(obj[key]) : obj[key];
    }
  }
  return res;
}

/**
 * Fetch data from API and handle large JSON by converting to Excel file.
 * @param {string} url - API endpoint
 * @param {number} recordThreshold - Max records before switching to Excel
 */
async function fetchData(url, recordThreshold = 10) {
  try {
    const response = await axios.get(url);
    const data = response.data;

    if (Array.isArray(data) && data.length > recordThreshold) {
      console.log(`Record count ${data.length} exceeds threshold. Generating Excel file...`);

      const workbook = new ExcelJS.Workbook();
      const worksheet = workbook.addWorksheet("Data");

      // Collect all unique keys from flattened objects
      const allKeys = new Set();
      const flattenedData = data.map(item =>
        typeof item === "object" && item !== null ? flattenObject(item) : { value: item }
      );

      flattenedData.forEach(item => {
        Object.keys(item).forEach(k => allKeys.add(k));
      });

      worksheet.columns = [...allKeys].map(key => ({ header: key, key }));

      // Add rows
      flattenedData.forEach(row => worksheet.addRow(row));

      const filePath = path.join(__dirname, "output.xlsx");
      await workbook.xlsx.writeFile(filePath);

      console.log(`Excel file saved at: ${filePath}`);
      return { filePath }; // Returning path to file
    } else {
      console.log("Returning JSON (small number of records).");
      return data;
    }
  } catch (error) {
    console.error("Error fetching data:", error.message);
    throw error;
  }
}

// Example usage:
(async () => {
  const result = await fetchData("https://jsonplaceholder.typicode.com/users", 10);
  console.log(result);
})();
