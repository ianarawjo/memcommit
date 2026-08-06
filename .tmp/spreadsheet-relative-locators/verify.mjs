import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const files = [
  "/Users/KimMunyeong/Github/memcommit/outputs/019fd250-522b-74b0-b4c6-f1f067ba02c1/mem-command-cheatsheet-ko.xlsx",
  "/Users/KimMunyeong/Github/memcommit/outputs/019fd250-522b-74b0-b4c6-f1f067ba02c1/mem-command-cheatsheet-multilingual.xlsx",
];

for (const file of files) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(file));
  const values = await workbook.inspect({
    kind: "table",
    range: "'Context Locators'!A1:E18",
    include: "values,formulas",
    tableMaxRows: 20,
    tableMaxCols: 6,
    maxChars: 10000,
  });
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "final formula error scan",
  });
  console.log(`VERIFY ${file}`);
  console.log(values.ndjson);
  console.log(errors.ndjson);
  for (const sheet of workbook.worksheets.items) {
    const preview = await workbook.render({
      sheetName: sheet.name,
      autoCrop: "all",
      scale: 1,
      format: "png",
    });
    const safe = `final-${file.split("/").pop().replace(".xlsx", "")}-${sheet.name.replaceAll("/", "-")}.png`;
    await fs.writeFile(safe, new Uint8Array(await preview.arrayBuffer()));
  }
}
