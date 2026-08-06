import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const outputDir = "/Users/KimMunyeong/Github/memcommit/outputs/019fd250-522b-74b0-b4c6-f1f067ba02c1";
const inputs = [
  {
    source: "/Users/KimMunyeong/Github/memcommit/outputs/019fc850-f177-7233-bba9-1fb6da3419ff/mem-command-cheatsheet-ko.xlsx",
    output: "mem-command-cheatsheet-ko.xlsx",
  },
  {
    source: "/Users/KimMunyeong/Github/memcommit/outputs/019fc850-f177-7233-bba9-1fb6da3419ff/mem-command-cheatsheet-multilingual.xlsx",
    output: "mem-command-cheatsheet-multilingual.xlsx",
  },
];

const rows = [
  ["Canonical name", "task-1/campus-wiki", "항상 같은 전역 Context를 가리킴", "Always addresses the same global Context", "mem ls task-1/campus-wiki"],
  [".", ".", "현재 Context", "Current Context", "mem ls ."],
  ["./", "./building-access", "현재 Context의 자식", "Child of the current Context", "mem ls ./building-access"],
  ["..", "..", "부모 Context 한 단계", "Parent Context, one level up", "mem switch .."],
  ["../", "../route-changes", "부모 아래의 형제 Context", "Sibling under the parent", "mem ls ../route-changes"],
  ["../../", "../../campus-wiki", "두 단계 위에서 campus-wiki 선택", "Select campus-wiki from two levels up", "mem ls ../../campus-wiki"],
  ["Bare name", "campus-wiki", "현재 위치 기준이 아닌 전역 이름", "Global name, not relative to current", "mem switch campus-wiki"],
  ["Not syntax", ".../campus-wiki", "점 세 개는 이동 문법이 아님; 문자 그대로 조회", "Three dots are literal text, not navigation", "→ Context '.../campus-wiki' not found"],
  ["Granted view", "task-1/campus-wiki", "현재 제한: Authority/granted view는 canonical 이름 사용", "Current limitation: use the canonical public name for granted views", "mem update --to task-1/campus-wiki"],
];

function addLocatorSheet(workbook) {
  const sheet = workbook.worksheets.add("Context Locators");
  sheet.showGridLines = false;
  sheet.getRange("A1:E1").merge();
  sheet.getRange("A1").values = [["mem CONTEXT LOCATORS · 상대주소 빠른 참조 / RELATIVE ADDRESS QUICK REFERENCE"]];
  sheet.getRange("A2:E2").merge();
  sheet.getRange("A2").values = [["기준 예시 / Base: task-1/participant/construction-updates  ·  각 ../ 는 이름 공간에서 부모 한 단계입니다."]];
  sheet.getRange("A4:E13").values = [
    ["종류 / TYPE", "입력 / LOCATOR", "한국어 의미", "ENGLISH MEANING", "예시 / EXAMPLE"],
    ...rows,
  ];
  const table = sheet.tables.add("A4:E13", true, "ContextLocatorReference");
  table.style = "TableStyleMedium2";
  table.showBandedRows = true;
  table.showFilterButton = false;

  sheet.getRange("A15:E15").merge();
  sheet.getRange("A15").values = [["사용 경계 / IMPORTANT BOUNDARIES"]];
  sheet.getRange("A16:E18").values = [
    ["• 상대 문법은 기존 ordinary Context를 찾는 operand에 사용합니다.", null, "Use relative syntax for operands that locate an existing ordinary Context.", null, null],
    ["• init, branch, rename의 새 이름처럼 새 Context 식별자를 만드는 자리에는 사용하지 않습니다.", null, "Do not use it for new identifiers such as init, branch, or rename's new name.", null, null],
    ["• mem update는 --from 또는 --to 중 하나가 필요합니다.", null, "mem update requires at least one of --from or --to.", null, null],
  ];
  sheet.getRange("A16:B16").merge();
  sheet.getRange("C16:E16").merge();
  sheet.getRange("A17:B17").merge();
  sheet.getRange("C17:E17").merge();
  sheet.getRange("A18:B18").merge();
  sheet.getRange("C18:E18").merge();

  sheet.getRange("A1:E1").format = {
    fill: "#1F1F1F",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    verticalAlignment: "center",
  };
  sheet.getRange("A2:E2").format = {
    fill: "#D9D9D9",
    font: { color: "#222222", italic: true },
    verticalAlignment: "center",
  };
  sheet.getRange("A15:E15").format = {
    fill: "#3B3B3B",
    font: { bold: true, color: "#FFFFFF" },
  };
  sheet.getRange("A16:E18").format = {
    fill: "#F2F2F2",
    font: { color: "#222222" },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "inside", style: "thin", color: "#D0D0D0" },
  };
  sheet.getRange("A5:E13").format.wrapText = true;
  sheet.getRange("A1:E18").format.font = { name: "Arial", color: "#222222" };
  sheet.getRange("A1:E1").format.font = { name: "Arial", bold: true, color: "#FFFFFF", size: 16 };
  sheet.getRange("A4:E4").format.font = { name: "Arial", bold: true, color: "#FFFFFF" };
  sheet.getRange("A15:E15").format.font = { name: "Arial", bold: true, color: "#FFFFFF" };
  sheet.getRange("A1:E1").format.rowHeight = 28;
  sheet.getRange("A2:E2").format.rowHeight = 24;
  sheet.getRange("A4:E4").format.rowHeight = 26;
  sheet.getRange("A5:E13").format.rowHeight = 38;
  sheet.getRange("A15:E15").format.rowHeight = 24;
  sheet.getRange("A16:E18").format.rowHeight = 34;
  sheet.getRange("A:A").format.columnWidth = 18;
  sheet.getRange("B:B").format.columnWidth = 28;
  sheet.getRange("C:C").format.columnWidth = 40;
  sheet.getRange("D:D").format.columnWidth = 43;
  sheet.getRange("E:E").format.columnWidth = 43;
  sheet.freezePanes.freezeRows(4);
  return sheet;
}

await fs.mkdir(outputDir, { recursive: true });
for (const item of inputs) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(item.source));
  addLocatorSheet(workbook);
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(`${outputDir}/${item.output}`);
}
