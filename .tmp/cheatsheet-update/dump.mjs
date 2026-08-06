import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const [inputPath, sheetName, rangeAddress] = process.argv.slice(2);
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItem(sheetName);
console.log(JSON.stringify(sheet.getRange(rangeAddress).values, null, 2));
