import { Workbook } from "@oai/artifact-tool";

const workbook = Workbook.create();
workbook.worksheets.add("Sheet1");
console.log(
  workbook.help("range.insert", {
    include: "index,examples,notes",
    maxChars: 5000,
  }).ndjson,
);
