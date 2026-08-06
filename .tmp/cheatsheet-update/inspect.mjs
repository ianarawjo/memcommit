import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = process.argv[2];
const previewDir = process.argv[3];
if (!inputPath || !previewDir) {
  throw new Error("usage: node inspect.mjs INPUT.xlsx PREVIEW_DIR");
}

await fs.mkdir(previewDir, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const overview = await workbook.inspect({
  kind: "workbook,sheet,table,drawing",
  include: "id,name,values,formulas",
  maxChars: 30000,
  tableMaxRows: 200,
  tableMaxCols: 20,
  tableMaxCellChars: 300,
});
console.log(overview.ndjson);

const sheets = workbook.worksheets.items;
for (const sheet of sheets) {
  const used = sheet.getUsedRange();
  const region = await workbook.inspect({
    kind: "region",
    sheetId: sheet.name,
    range: used.address.split("!").at(-1),
    include: "values,formulas",
    maxChars: 100000,
    tableMaxRows: 500,
    tableMaxCols: 30,
    tableMaxCellChars: 1000,
  });
  console.log(`SHEET_DATA ${sheet.name}`);
  console.log(region.ndjson);
  const preview = await workbook.render({
    sheetName: sheet.name,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  const safeName = sheet.name.replaceAll(/[^a-zA-Z0-9_-]/g, "_");
  await fs.writeFile(
    `${previewDir}/${safeName}.png`,
    new Uint8Array(await preview.arrayBuffer()),
  );
}
