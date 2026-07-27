/**
 * ONE-TIME ingest: NIST CSF 2.0 CPRT catalog (XLSX) -> framework-neutral core JSON.
 *
 * This script does NOT ship inside the skill. Only its output does. It is therefore
 * exempt from the repo's stdlib-only Python rule and runs on node + SheetJS, reusing
 * the xlsx module already installed in the csf-assessment project.
 *
 * Source:  tools/csf-2.0.xlsx (vendored NIST CPRT export; sha256 recorded in the output)
 * Model:   csf-assessment/scripts/ingest-csf.ts documents the row shape and the
 *          [Withdrawn:] exclusion rule; this script additionally captures columns
 *          D (Implementation Examples) and E (Informative References), which that
 *          ingest deliberately skipped.
 *
 * Run from the repo root (after `npm install --prefix tools`):
 *   node <this file> <out-path> [path/to/csf-2.0.xlsx]
 */
const XLSX = require("xlsx");
const { writeFileSync, readFileSync } = require("node:fs");
const { createHash } = require("node:crypto");

const SOURCE_XLSX = process.argv[3] || require("node:path").join(__dirname, "csf-2.0.xlsx");
const SHEET = "CSF 2.0";
const OUT = process.argv[2];
if (!OUT) { console.error("usage: node ingest-csf-core.js <out-path> [xlsx-path]"); process.exit(2); }

const FUNCTION_ORDER = ["GV", "ID", "PR", "DE", "RS", "RC"];
const EXPECTED_PER_FUNCTION = { GV: 31, ID: 21, PR: 22, DE: 11, RS: 13, RC: 8 };

// Row patterns. Descriptor is optional so bare "GOVERN (GV)" section terminators are
// recognised and skipped rather than silently parsed as a second function.
const RE_FUNCTION = /^(.+?) \(([A-Z]{2})\)(?::\s*([\s\S]+))?$/;
const RE_CATEGORY = /^(.+?) \(([A-Z]{2}\.[A-Z]{2})\)(?::\s*([\s\S]+))?$/;
const RE_SUBCATEGORY = /^([A-Z]{2}\.[A-Z]{2}-\d{2}):\s*([\s\S]+)$/;

const withdrawn = (s) => s.includes("[Withdrawn");

/** Column D: "Ex1: ...\nEx2: ..." -> ["...", "..."]. */
function parseExamples(cell) {
  const text = (cell || "").toString().trim();
  if (!text) return [];
  return text
    .split(/\s*(?:\r?\n)?\s*Ex\d+:\s*/)
    .map((s) => s.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

/**
 * Column E: newline-separated reference lines. Stored RAW.
 *
 * Deliberate: a line like "ISO/IEC 27001:2022: Mandatory Clause: 4.1" carries colons
 * inside the source name, so splitting source from reference is guesswork against an
 * open-ended set of catalogs. v1 ships this data dormant (rendered in v2), and a
 * fragile parse baked in now would be harder to correct later than no parse at all.
 * v2's crosswalk work owns the structured split.
 */
function parseReferences(cell) {
  return (cell || "").toString().split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
}

const rows = XLSX.utils.sheet_to_json(XLSX.readFile(SOURCE_XLSX).Sheets[SHEET], {
  header: 1, defval: "", blankrows: true,
});

const functions = [];
let curFn = null, curCat = null;
const skipped = { functionTerminators: 0, withdrawnCategories: 0, withdrawnSubcategories: 0 };

for (let i = 2; i < rows.length; i++) {
  const row = rows[i] || [];
  const a = (row[0] || "").toString().trim();
  const b = (row[1] || "").toString().trim();
  const c = (row[2] || "").toString().trim();
  const examples = parseExamples(row[3]);
  const references = parseReferences(row[4]);

  if (a) {
    const m = RE_FUNCTION.exec(a);
    if (!m) throw new Error(`row ${i + 1}: unparseable Function cell: ${a}`);
    const [, name, id, description] = m;
    if (!description) { skipped.functionTerminators++; continue; }  // bare section terminator
    if (!FUNCTION_ORDER.includes(id)) throw new Error(`row ${i + 1}: unknown Function id ${id}`);
    curFn = {
      id,
      name: name.replace(/\s+/g, " ").trim(),
      description: description.replace(/\s+/g, " ").trim(),
      informativeReferences: references,
      categories: [],
    };
    curCat = null;
    functions.push(curFn);
    continue;
  }

  if (b) {
    if (withdrawn(b)) { skipped.withdrawnCategories++; curCat = null; continue; }
    const m = RE_CATEGORY.exec(b);
    if (!m) throw new Error(`row ${i + 1}: unparseable Category cell: ${b}`);
    const [, name, id, description] = m;
    if (!curFn) throw new Error(`row ${i + 1}: category ${id} before any function`);
    if (!id.startsWith(curFn.id + ".")) throw new Error(`row ${i + 1}: category ${id} outside function ${curFn.id}`);
    curCat = {
      id,
      name: name.replace(/\s+/g, " ").trim(),
      description: (description || "").replace(/\s+/g, " ").trim(),
      informativeReferences: references,
      subcategories: [],
    };
    curFn.categories.push(curCat);
    continue;
  }

  if (c) {
    if (withdrawn(c)) { skipped.withdrawnSubcategories++; continue; }
    const m = RE_SUBCATEGORY.exec(c);
    if (!m) throw new Error(`row ${i + 1}: unparseable Subcategory cell: ${c}`);
    const [, id, text] = m;
    if (!curCat) throw new Error(`row ${i + 1}: subcategory ${id} before any category`);
    if (!id.startsWith(curCat.id + "-")) throw new Error(`row ${i + 1}: subcategory ${id} outside category ${curCat.id}`);
    curCat.subcategories.push({
      id,
      text: text.replace(/\s+/g, " ").trim(),
      examples,
      informativeReferences: references,
    });
  }
}

// ---- Integrity assertions. Fail before writing, never after. ----
const problems = [];
const check = (cond, msg) => { if (!cond) problems.push(msg); };

const cats = functions.flatMap((f) => f.categories);
const subs = cats.flatMap((c) => c.subcategories);

check(functions.length === 6, `expected 6 functions, got ${functions.length}`);
check(cats.length === 22, `expected 22 categories, got ${cats.length}`);
check(subs.length === 106, `expected 106 subcategories, got ${subs.length}`);

const order = functions.map((f) => f.id).join(",");
check(order === FUNCTION_ORDER.join(","), `unexpected function order: ${order}`);

for (const f of functions) {
  const n = f.categories.reduce((acc, c) => acc + c.subcategories.length, 0);
  check(n === EXPECTED_PER_FUNCTION[f.id], `${f.id}: expected ${EXPECTED_PER_FUNCTION[f.id]} subcategories, got ${n}`);
}

const ids = subs.map((s) => s.id);
check(new Set(ids).size === ids.length, "duplicate subcategory ids");
const catIds = cats.map((c) => c.id);
check(new Set(catIds).size === catIds.length, "duplicate category ids");

const exampleCount = subs.reduce((acc, s) => acc + s.examples.length, 0);
check(exampleCount === 363, `expected 363 implementation examples, got ${exampleCount}`);

const noExamples = subs.filter((s) => s.examples.length === 0).map((s) => s.id);
check(noExamples.length === 0, `subcategories with no implementation example: ${noExamples.join(", ")}`);

const empty = subs.filter((s) => !s.text).map((s) => s.id);
check(empty.length === 0, `subcategories with empty text: ${empty.join(", ")}`);

if (problems.length) {
  console.error("INGEST FAILED — integrity assertions did not hold:");
  for (const p of problems) console.error("  - " + p);
  process.exit(1);
}

const core = {
  id: "nist-csf-2.0",
  name: "NIST Cybersecurity Framework",
  version: "2.0",
  // Provenance is recorded by content hash rather than a timestamp so that
  // regenerating from the same source produces a byte-identical file.
  source: {
    publication: "NIST CSWP 29 — The NIST Cybersecurity Framework (CSF) 2.0",
    catalog: "NIST Cybersecurity and Privacy Reference Tool (CPRT) CSF 2.0 export",
    file: "csf-2.0.xlsx",
    sha256: createHash("sha256").update(readFileSync(SOURCE_XLSX)).digest("hex"),
    note: "NIST publications are US Government works and are not subject to copyright.",
  },
  notes: {
    informativeReferences:
      "Stored as raw catalog lines exactly as published. Structured splitting into " +
      "{source, reference} is deferred to the v2 crosswalk work: source names such as " +
      "'ISO/IEC 27001:2022' contain colons, so any split rule would be guesswork against " +
      "an open-ended set of catalogs. v1 carries this data but does not render it.",
    tiers: "Populated by T0b from NIST CSWP 29. Tiers characterise rigor, never a maturity score.",
  },
  tiers: null,
  hierarchy: functions,
};

writeFileSync(OUT, JSON.stringify(core, null, 2) + "\n");

console.log("OK");
console.log(`  functions      ${functions.length}`);
console.log(`  categories     ${cats.length}`);
console.log(`  subcategories  ${subs.length}  (${functions.map((f) => `${f.id}:${f.categories.reduce((a, c) => a + c.subcategories.length, 0)}`).join(" ")})`);
console.log(`  examples       ${exampleCount}  (min per subcategory: ${Math.min(...subs.map((s) => s.examples.length))})`);
console.log(`  subs w/ refs   ${subs.filter((s) => s.informativeReferences.length).length}`);
console.log(`  skipped        ${skipped.functionTerminators} function terminators, ${skipped.withdrawnCategories} withdrawn categories, ${skipped.withdrawnSubcategories} withdrawn subcategories`);
console.log(`  -> ${OUT}`);
