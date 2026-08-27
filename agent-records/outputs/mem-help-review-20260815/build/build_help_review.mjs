import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const repoRoot = "/Users/KimMunyeong/Github/memcommit";
const outputRoot = path.join(repoRoot, "agent-records/outputs/mem-help-review-20260815");
const previewRoot = path.join(outputRoot, "build/previews");

const extractScript = String.raw`
import json
import subprocess

from memcommit.adapters.console.commands.help_inventory import HELP_CATEGORY_GROUPS, COMMAND_FORMS
from memcommit.help_catalog import OPERATION_HELP_BY_NAME

rows = []
for category, names in HELP_CATEGORY_GROUPS:
    for name in names:
        operation = OPERATION_HELP_BY_NAME[name]
        rows.append({
            "category": category,
            "name": name,
            "summary": operation.summary,
            "flow": operation.flow,
            "execution": operation.execution.value,
            "effect": operation.effect,
            "range": operation.range or "",
            "forms": list(COMMAND_FORMS.get(name, ())),
        })

head = subprocess.check_output(
    ["git", "rev-parse", "--short", "HEAD"], text=True
).strip()
dirty = bool(subprocess.check_output(
    [
        "git", "status", "--porcelain", "--",
        "memcommit/help_catalog/catalog.py",
        "memcommit/adapters/console/commands/help_inventory.py",
    ],
    text=True,
).strip())
print(json.dumps({"head": head, "dirty": dirty, "rows": rows}))
`;

const extracted = JSON.parse(
  execFileSync("python", ["-c", extractScript], {
    cwd: repoRoot,
    encoding: "utf8",
  }),
);

const palette = {
  navy: "#17233C",
  navy2: "#263A5B",
  white: "#FFFFFF",
  text: "#25313F",
  muted: "#667085",
  line: "#D6DCE5",
  current: "#F3F5F7",
  editable: "#FFF7D6",
  name: "#DCE6F1",
  llm: "#FCE4D6",
  flow: "#DDEBF7",
  explanation: "#FFF2CC",
  boundary: "#FDE9E7",
  bestFor: "#E2F0D9",
  ready: "#E2F0D9",
  needs: "#FFF2CC",
  approved: "#C6E0B4",
};

const workbook = Workbook.create();
const compact = workbook.worksheets.add("Compact Review");
const contract = workbook.worksheets.add("Contract Review");
const snapshot = workbook.worksheets.add("Catalog Snapshot");
const legend = workbook.worksheets.add("Legend");

const operationCount = extracted.rows.length;
const firstDataRow = 5;
const lastDataRow = firstDataRow + operationCount - 1;
const generatedAt = new Date().toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
const sourceState = `Generated from current Help catalog · git ${extracted.head}${extracted.dirty ? " · Help files have uncommitted changes" : " · clean Help files"} · ${operationCount} operations · ${generatedAt}`;

function titleBand(sheet, endColumn, title, subtitle) {
  sheet.mergeCells(`A1:${endColumn}1`);
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A1:${endColumn}1`).format = {
    fill: palette.navy,
    font: { name: "Aptos Display", size: 18, bold: true, color: palette.white },
    verticalAlignment: "center",
  };
  sheet.getRange("A1").format.rowHeight = 32;

  sheet.mergeCells(`A2:${endColumn}2`);
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${endColumn}2`).format = {
    fill: "#E9EEF5",
    font: { name: "Aptos", size: 10, color: palette.text },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("A2").format.rowHeight = 34;

  sheet.mergeCells(`A3:${endColumn}3`);
  sheet.getRange("A3").values = [[sourceState]];
  sheet.getRange(`A3:${endColumn}3`).format = {
    fill: "#F8FAFC",
    font: { name: "Aptos", size: 9, italic: true, color: palette.muted },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange("A3").format.rowHeight = 24;
  sheet.showGridLines = false;
}

function styleHeader(range, fills = null) {
  range.format = {
    fill: palette.navy2,
    font: { name: "Aptos", size: 10, bold: true, color: palette.white },
    wrapText: true,
    verticalAlignment: "center",
    horizontalAlignment: "left",
    borders: { preset: "outside", style: "thin", color: palette.navy },
  };
  if (fills) {
    for (const [cell, fill, color = palette.text] of fills) {
      range.worksheet.getRange(cell).format = {
        fill,
        font: { name: "Aptos", size: 10, bold: true, color },
        wrapText: true,
        verticalAlignment: "center",
      };
    }
  }
}

function applyBodyFormat(range, fill = palette.white) {
  range.format = {
    fill,
    font: { name: "Aptos", size: 10, color: palette.text },
    wrapText: true,
    verticalAlignment: "top",
    horizontalAlignment: "left",
    borders: {
      insideHorizontal: { style: "thin", color: palette.line },
      bottom: { style: "thin", color: palette.line },
    },
  };
}

// Raw snapshot: this sheet is generated from Python Help metadata and is not
// intended to be edited. It makes the workbook's provenance auditable.
titleBand(
  snapshot,
  "J",
  "Mem Help · Catalog Snapshot",
  "Read-only snapshot of the current Python Help catalog. Regenerate the workbook after code changes; do not treat this sheet as the Help source of truth.",
);
snapshot.getRange("A4:J4").values = [[
  "CATEGORY",
  "NAME",
  "SUMMARY",
  "FLOW",
  "EXECUTION",
  "EFFECT",
  "RANGE",
  "FORMS",
  "CATALOG SOURCE",
  "FORMS SOURCE",
]];
styleHeader(snapshot.getRange("A4:J4"));
const snapshotRows = extracted.rows.map((row) => [
  row.category,
  row.name,
  row.summary,
  row.flow,
  row.execution,
  row.effect,
  row.range,
  row.forms.join("\n"),
  "memcommit/help_catalog/catalog.py",
  "memcommit/adapters/console/commands/help_inventory.py",
]);
snapshot.getRange(`A${firstDataRow}:J${lastDataRow}`).values = snapshotRows;
applyBodyFormat(snapshot.getRange(`A${firstDataRow}:J${lastDataRow}`), palette.current);
snapshot.getRange(`A${firstDataRow}:J${lastDataRow}`).format.rowHeight = 58;
snapshot.getRange("A:A").format.columnWidth = 22;
snapshot.getRange("B:B").format.columnWidth = 19;
snapshot.getRange("C:C").format.columnWidth = 52;
snapshot.getRange("D:D").format.columnWidth = 40;
snapshot.getRange("E:E").format.columnWidth = 17;
snapshot.getRange("F:F").format.columnWidth = 43;
snapshot.getRange("G:G").format.columnWidth = 39;
snapshot.getRange("H:H").format.columnWidth = 63;
snapshot.getRange("I:J").format.columnWidth = 38;
snapshot.freezePanes.freezeRows(4);
snapshot.freezePanes.freezeColumns(2);
const snapshotTable = snapshot.tables.add(`A4:J${lastDataRow}`, true, "HelpCatalogSnapshot");
snapshotTable.style = "TableStyleMedium2";
snapshotTable.showBandedRows = true;

// Expanded review: current fields are formula-linked from the snapshot, while
// yellow/red/green proposal columns are the human review workspace.
titleBand(
  contract,
  "Q",
  "Mem Help · Expanded Contract Review",
  "Keep structured semantics separate here. Proposed Flow(s) may contain multiple labelled lines. Proposed fields drive the Compact Review sheet.",
);
contract.getRange("A4:Q4").values = [[
  "CATEGORY",
  "NAME",
  "CURRENT EXECUTION",
  "LLM DISPLAY",
  "CURRENT FLOW",
  "PROPOSED FLOW(S)",
  "CURRENT SUMMARY",
  "PROPOSED EXPLANATION",
  "CURRENT EFFECT",
  "PROPOSED BOUNDARY",
  "CURRENT RANGE",
  "PROPOSED BEST FOR",
  "FORMS",
  "DECISION",
  "REVIEW NOTES",
  "SOURCE",
  "COMPLETENESS",
]];
styleHeader(contract.getRange("A4:Q4"));

const contractFormulaRows = [];
const contractValueRows = [];
for (let index = 0; index < operationCount; index += 1) {
  const rowNumber = firstDataRow + index;
  const sourceRow = firstDataRow + index;
  const name = extracted.rows[index].name;
  const isMerge = name === "merge";
  contractFormulaRows.push([
    `='Catalog Snapshot'!A${sourceRow}`,
    `='Catalog Snapshot'!B${sourceRow}`,
    `='Catalog Snapshot'!E${sourceRow}`,
    `=IF(C${rowNumber}="DETERMINISTIC","NO",IF(C${rowNumber}="SEMANTIC","YES — CACHE OR PROVIDER","DEPENDS ON FORM"))`,
    `='Catalog Snapshot'!D${sourceRow}`,
    null,
    `='Catalog Snapshot'!C${sourceRow}`,
    null,
    `='Catalog Snapshot'!F${sourceRow}`,
    null,
    `='Catalog Snapshot'!G${sourceRow}`,
    null,
    `='Catalog Snapshot'!H${sourceRow}`,
    null,
    null,
    `='Catalog Snapshot'!I${sourceRow}`,
    `=IF(AND(H${rowNumber}<>"",J${rowNumber}<>"",L${rowNumber}<>""),"READY FOR WORDING REVIEW","NEEDS DRAFT")`,
  ]);
  contractValueRows.push([
    null,
    null,
    null,
    null,
    null,
    isMerge
      ? "DIRECT · Source direct items → current Target Context\nRECURSIVE · Source subtree → matching relative paths in the current Target subtree"
      : "",
    null,
    isMerge
      ? "Adds a Source item only when its stored identity is absent from the Target."
      : "",
    null,
    isMerge
      ? "Existing Target items remain unchanged. Items already present by identity are not added again; Source edits, deletions, and content conflicts are not resolved."
      : "",
    null,
    "",
    null,
    "Not reviewed",
    isMerge
      ? "Boundary and plural Flow are seeded from the current design review. Best For intentionally remains open."
      : "",
    null,
    null,
  ]);
}
contract.getRange(`A${firstDataRow}:Q${lastDataRow}`).formulas = contractFormulaRows;
// Write only editable values after formulas so the proposal cells remain plain
// workbook inputs and the linked current fields remain auditable formulas.
for (let index = 0; index < contractValueRows.length; index += 1) {
  const rowNumber = firstDataRow + index;
  const values = contractValueRows[index];
  contract.getRange(`F${rowNumber}`).values = [[values[5]]];
  contract.getRange(`H${rowNumber}`).values = [[values[7]]];
  contract.getRange(`J${rowNumber}`).values = [[values[9]]];
  contract.getRange(`L${rowNumber}`).values = [[values[11]]];
  contract.getRange(`N${rowNumber}`).values = [[values[13]]];
  contract.getRange(`O${rowNumber}`).values = [[values[14]]];
}

applyBodyFormat(contract.getRange(`A${firstDataRow}:Q${lastDataRow}`), palette.white);
contract.getRange(`A${firstDataRow}:E${lastDataRow}`).format.fill = palette.current;
contract.getRange(`G${firstDataRow}:G${lastDataRow}`).format.fill = palette.current;
contract.getRange(`I${firstDataRow}:I${lastDataRow}`).format.fill = palette.current;
contract.getRange(`K${firstDataRow}:K${lastDataRow}`).format.fill = palette.current;
contract.getRange(`M${firstDataRow}:M${lastDataRow}`).format.fill = palette.current;
contract.getRange(`P${firstDataRow}:Q${lastDataRow}`).format.fill = palette.current;
contract.getRange(`F${firstDataRow}:F${lastDataRow}`).format.fill = palette.flow;
contract.getRange(`H${firstDataRow}:H${lastDataRow}`).format.fill = palette.explanation;
contract.getRange(`J${firstDataRow}:J${lastDataRow}`).format.fill = palette.boundary;
contract.getRange(`L${firstDataRow}:L${lastDataRow}`).format.fill = palette.bestFor;
contract.getRange(`N${firstDataRow}:O${lastDataRow}`).format.fill = palette.editable;
contract.getRange(`A${firstDataRow}:Q${lastDataRow}`).format.rowHeight = 76;
contract.getRange("A:A").format.columnWidth = 21;
contract.getRange("B:B").format.columnWidth = 18;
contract.getRange("C:C").format.columnWidth = 19;
contract.getRange("D:D").format.columnWidth = 25;
contract.getRange("E:E").format.columnWidth = 39;
contract.getRange("F:F").format.columnWidth = 48;
contract.getRange("G:G").format.columnWidth = 48;
contract.getRange("H:H").format.columnWidth = 50;
contract.getRange("I:I").format.columnWidth = 44;
contract.getRange("J:J").format.columnWidth = 55;
contract.getRange("K:K").format.columnWidth = 40;
contract.getRange("L:L").format.columnWidth = 52;
contract.getRange("M:M").format.columnWidth = 65;
contract.getRange("N:N").format.columnWidth = 18;
contract.getRange("O:O").format.columnWidth = 43;
contract.getRange("P:P").format.columnWidth = 39;
contract.getRange("Q:Q").format.columnWidth = 28;
contract.getRange(`N${firstDataRow}:N${lastDataRow}`).dataValidation = {
  rule: { type: "list", values: ["Not reviewed", "Draft", "Approved", "Rework"] },
};
contract.getRange(`D${firstDataRow}:D${lastDataRow}`).conditionalFormats.add(
  "containsText",
  { text: "YES", format: { fill: palette.llm, font: { bold: true, color: palette.text } } },
);
contract.getRange(`D${firstDataRow}:D${lastDataRow}`).conditionalFormats.add(
  "containsText",
  { text: "NO", format: { fill: palette.current, font: { bold: true, color: palette.text } } },
);
contract.getRange(`Q${firstDataRow}:Q${lastDataRow}`).conditionalFormats.add(
  "containsText",
  { text: "READY", format: { fill: palette.ready, font: { bold: true, color: "#385723" } } },
);
contract.getRange(`Q${firstDataRow}:Q${lastDataRow}`).conditionalFormats.add(
  "containsText",
  { text: "NEEDS", format: { fill: palette.needs, font: { bold: true, color: "#7F6000" } } },
);
contract.freezePanes.freezeRows(4);
contract.freezePanes.freezeColumns(2);
const contractTable = contract.tables.add(`A4:Q${lastDataRow}`, true, "HelpContractReview");
contractTable.style = "TableStyleMedium2";
contractTable.showBandedRows = false;

// Compact review: five semantic columns represent the planned wide TUI. A
// narrow TUI stacks these same fields as rows; no alternate wording source is
// introduced. Proposed fields fall back to the current catalog until drafted.
titleBand(
  compact,
  "E",
  "Mem Help · Responsive Compact Review",
  "Five semantic columns for wide terminals. A narrow terminal stacks the same fields as rows. Edit proposals in Contract Review; this sheet updates through formulas.",
);
compact.getRange("A4:E4").values = [[
  "NAME",
  "LLM",
  "FLOW(S)",
  "COMPACT EXPLANATION + BOUNDARY",
  "BEST FOR",
]];
styleHeader(compact.getRange("A4:E4"));
compact.getRange("A4").format.fill = palette.name;
compact.getRange("A4").format.font = { name: "Aptos", size: 10, bold: true, color: palette.text };
compact.getRange("B4").format.fill = palette.llm;
compact.getRange("B4").format.font = { name: "Aptos", size: 10, bold: true, color: palette.text };
compact.getRange("C4").format.fill = palette.flow;
compact.getRange("C4").format.font = { name: "Aptos", size: 10, bold: true, color: palette.text };
compact.getRange("D4").format.fill = palette.explanation;
compact.getRange("D4").format.font = { name: "Aptos", size: 10, bold: true, color: palette.text };
compact.getRange("E4").format.fill = palette.bestFor;
compact.getRange("E4").format.font = { name: "Aptos", size: 10, bold: true, color: palette.text };

const compactFormulaRows = [];
for (let rowNumber = firstDataRow; rowNumber <= lastDataRow; rowNumber += 1) {
  compactFormulaRows.push([
    `='Contract Review'!B${rowNumber}`,
    `='Contract Review'!D${rowNumber}`,
    `=IF('Contract Review'!F${rowNumber}<>"",'Contract Review'!F${rowNumber},'Contract Review'!E${rowNumber})`,
    `=IF('Contract Review'!H${rowNumber}<>"",'Contract Review'!H${rowNumber},'Contract Review'!G${rowNumber})&IF('Contract Review'!J${rowNumber}<>""," · Boundary: "&'Contract Review'!J${rowNumber},"")`,
    `=IF('Contract Review'!L${rowNumber}<>"",'Contract Review'!L${rowNumber},"— draft needed —")`,
  ]);
}
compact.getRange(`A${firstDataRow}:E${lastDataRow}`).formulas = compactFormulaRows;
applyBodyFormat(compact.getRange(`A${firstDataRow}:A${lastDataRow}`), palette.name);
applyBodyFormat(compact.getRange(`B${firstDataRow}:B${lastDataRow}`), palette.llm);
applyBodyFormat(compact.getRange(`C${firstDataRow}:C${lastDataRow}`), palette.flow);
applyBodyFormat(compact.getRange(`D${firstDataRow}:D${lastDataRow}`), palette.explanation);
applyBodyFormat(compact.getRange(`E${firstDataRow}:E${lastDataRow}`), palette.bestFor);
compact.getRange(`A${firstDataRow}:E${lastDataRow}`).format.rowHeight = 68;
compact.getRange("A:A").format.columnWidth = 23;
compact.getRange("B:B").format.columnWidth = 25;
compact.getRange("C:C").format.columnWidth = 51;
compact.getRange("D:D").format.columnWidth = 78;
compact.getRange("E:E").format.columnWidth = 60;
compact.getRange(`B${firstDataRow}:B${lastDataRow}`).conditionalFormats.add(
  "containsText",
  { text: "YES", format: { fill: palette.llm, font: { bold: true, color: palette.text } } },
);
compact.getRange(`B${firstDataRow}:B${lastDataRow}`).conditionalFormats.add(
  "containsText",
  { text: "NO", format: { fill: palette.current, font: { bold: true, color: palette.text } } },
);
compact.freezePanes.freezeRows(4);
compact.freezePanes.freezeColumns(1);

// Legend and responsive projection sketch.
titleBand(
  legend,
  "F",
  "Mem Help · Review Legend",
  "The workbook is a review surface generated from code. Final wording is implemented in the Help catalog and then regenerated here for verification.",
);
legend.mergeCells("A4:F4");
legend.getRange("A4").values = [["WIDE TERMINAL · FIVE COLUMNS"]];
legend.getRange("A4:F4").format = {
  fill: palette.navy2,
  font: { name: "Aptos", size: 11, bold: true, color: palette.white },
};
legend.getRange("A5:E5").values = [["NAME", "LLM", "FLOW(S)", "COMPACT EXPLANATION + BOUNDARY", "BEST FOR"]];
legend.getRange("A6:E6").values = [[
  "merge",
  "NO",
  "Source → current Target",
  "Add only Source identities absent from the Target; existing Target items remain unchanged.",
  "A concrete situation belongs here; Merge is intentionally still under review.",
]];
for (const [range, fill] of [["A5:A6", palette.name], ["B5:B6", palette.llm], ["C5:C6", palette.flow], ["D5:D6", palette.explanation], ["E5:E6", palette.bestFor]]) {
  applyBodyFormat(legend.getRange(range), fill);
}
legend.getRange("A5:E5").format.font = { name: "Aptos", size: 10, bold: true, color: palette.text };
legend.getRange("A6:E6").format.rowHeight = 54;

legend.mergeCells("A8:F8");
legend.getRange("A8").values = [["NARROW TERMINAL · SAME FIELDS STACKED AS ROWS"]];
legend.getRange("A8:F8").format = {
  fill: palette.navy2,
  font: { name: "Aptos", size: 11, bold: true, color: palette.white },
};
legend.getRange("A9:B13").values = [
  ["NAME", "merge"],
  ["LLM", "NO"],
  ["FLOW(S)", "Source → current Target"],
  ["EXPLANATION", "Add only Source identities absent from the Target; existing Target items remain unchanged."],
  ["BEST FOR", "A concrete situation belongs here; Merge is intentionally still under review."],
];
applyBodyFormat(legend.getRange("A9:B13"), palette.white);
legend.getRange("A9:A13").format = {
  fill: "#E9EEF5",
  font: { name: "Aptos", size: 10, bold: true, color: palette.text },
  wrapText: true,
  verticalAlignment: "top",
};
legend.getRange("A9:B13").format.rowHeight = 40;

legend.mergeCells("A15:F15");
legend.getRange("A15").values = [["FIELD CONTRACT"]];
legend.getRange("A15:F15").format = {
  fill: palette.navy2,
  font: { name: "Aptos", size: 11, bold: true, color: palette.white },
};
legend.getRange("A16:C22").values = [
  ["FIELD", "MEANING", "COLOR"],
  ["NAME", "Public operation name.", "Blue-gray"],
  ["LLM", "NO, YES — CACHE OR PROVIDER, or DEPENDS ON FORM.", "Peach"],
  ["FLOW(S)", "One or more semantic input-to-output relationships; not every CLI spelling.", "Blue"],
  ["EXPLANATION", "What the operation does and why its distinction matters.", "Yellow"],
  ["BOUNDARY", "What remains unchanged, is skipped, or is deliberately not interpreted.", "Red tint"],
  ["BEST FOR", "A concrete situation in which this operation is the right choice.", "Green"],
];
styleHeader(legend.getRange("A16:C16"));
applyBodyFormat(legend.getRange("A17:C22"), palette.white);
legend.getRange("A17:A22").format.font = { name: "Aptos", size: 10, bold: true, color: palette.text };

legend.mergeCells("A24:F24");
legend.getRange("A24").values = [["REVIEW WORKFLOW"]];
legend.getRange("A24:F24").format = {
  fill: palette.navy2,
  font: { name: "Aptos", size: 11, bold: true, color: palette.white },
};
legend.getRange("A25:B29").values = [
  ["1", "Read the generated current contract in Catalog Snapshot."],
  ["2", "Draft plural Flow(s), Explanation, Boundary, and Best For in Contract Review."],
  ["3", "Inspect the formula-driven five-column projection in Compact Review."],
  ["4", "Mark Decision only after a novice can predict the operation, mutation boundary, and LLM route."],
  ["5", "Implement approved wording in Python Help, regenerate, and verify both BY KIND and A–Z."],
];
applyBodyFormat(legend.getRange("A25:B29"), palette.white);
legend.getRange("A25:A29").format = {
  fill: "#E9EEF5",
  font: { name: "Aptos", size: 10, bold: true, color: palette.text },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};

legend.getRange("A:A").format.columnWidth = 22;
legend.getRange("B:B").format.columnWidth = 55;
legend.getRange("C:C").format.columnWidth = 36;
legend.getRange("D:D").format.columnWidth = 72;
legend.getRange("E:E").format.columnWidth = 55;
legend.getRange("F:F").format.columnWidth = 3;
legend.freezePanes.freezeRows(3);

await fs.mkdir(previewRoot, { recursive: true });

const compactInspect = await workbook.inspect({
  kind: "table",
  range: `Compact Review!A1:E10`,
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 5,
  maxChars: 10000,
});
console.log("COMPACT_INSPECT");
console.log(compactInspect.ndjson);

const mergeIndex = extracted.rows.findIndex((row) => row.name === "merge");
const mergeRow = firstDataRow + mergeIndex;
const mergeInspect = await workbook.inspect({
  kind: "table",
  range: `Contract Review!A${mergeRow}:Q${mergeRow}`,
  include: "values,formulas",
  tableMaxRows: 2,
  tableMaxCols: 17,
  maxChars: 9000,
});
console.log("MERGE_INSPECT");
console.log(mergeInspect.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log("FORMULA_ERRORS");
console.log(errors.ndjson);

const renderSpecs = [
  ["Compact Review", "A1:E12", "compact-review.png"],
  ["Compact Review", `A${Math.max(firstDataRow, mergeRow - 1)}:E${mergeRow + 1}`, "compact-merge.png"],
  ["Contract Review", `A1:Q8`, "contract-review.png"],
  ["Contract Review", `A${mergeRow}:Q${mergeRow}`, "contract-merge.png"],
  ["Catalog Snapshot", "A1:J9", "catalog-snapshot.png"],
  ["Legend", "A1:F29", "legend.png"],
];
for (const [sheetName, range, fileName] of renderSpecs) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(
    path.join(previewRoot, fileName),
    new Uint8Array(await preview.arrayBuffer()),
  );
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(outputRoot, "mem-help-review.xlsx"));
console.log(`OUTPUT ${path.join(outputRoot, "mem-help-review.xlsx")}`);
console.log(`MERGE_ROW ${mergeRow}`);
