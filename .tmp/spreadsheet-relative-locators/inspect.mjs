import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputs = [
  "/Users/KimMunyeong/Github/memcommit/outputs/019fc850-f177-7233-bba9-1fb6da3419ff/mem-command-cheatsheet-ko.xlsx",
  "/Users/KimMunyeong/Github/memcommit/outputs/019fc850-f177-7233-bba9-1fb6da3419ff/mem-command-cheatsheet-multilingual.xlsx",
];

for (const input of inputs) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(input));
  const summary = await workbook.inspect({
    kind: "workbook,sheet,table",
    maxChars: 12000,
    tableMaxRows: 20,
    tableMaxCols: 12,
    tableMaxCellChars: 120,
  });
  console.log(`WORKBOOK ${input}`);
  console.log(summary.ndjson);
  for (const sheet of workbook.worksheets.items) {
    const used = sheet.getUsedRange();
    if (!used) continue;
    const preview = await workbook.render({
      sheetName: sheet.name,
      autoCrop: "all",
      scale: 1,
      format: "png",
    });
    const safe = `${input.split("/").pop().replace(".xlsx", "")}-${sheet.name.replaceAll("/", "-")}.png`;
    await fs.writeFile(safe, new Uint8Array(await preview.arrayBuffer()));
  }
}
