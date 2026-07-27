/**
 * ONE-TIME harvest: authored guidance IP from the csf-assessment web tool.
 *
 * Build-time only; does not ship. Extracts the hand-authored content — the actual
 * differentiator, as opposed to the NIST public-domain taxonomy — into JSON the
 * skill can load:
 *
 *   src/lib/assessment/guidance-deep.ts  -> deepGuidance  (15 per-Subcategory entries)
 *   src/lib/assessment/guidance.data.ts  -> tierTransitions, functionSlants, tierNames
 *   src/lib/frameworks/csf-2.0-context.ts-> functionContext (definition + whyItMatters)
 *
 * Extracts by stripping TypeScript annotations and evaluating the object literals,
 * rather than transcribing by hand: 15 multi-paragraph entries copied manually is a
 * near-certain source of silent drift, and re-running this proves the shipped JSON
 * still matches source.
 *
 * Run:
 *   node tools/harvest-guidance.js <csf-assessment-repo> <out.json>
 */
const { readFileSync, writeFileSync } = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const REPO = process.argv[2];
const OUT = process.argv[3];
if (!REPO || !OUT) {
  console.error("usage: node harvest-guidance.js <csf-assessment-repo> <out.json>");
  process.exit(2);
}

/** Evaluate a named exported object literal out of a TS module. */
function extract(file, exportName) {
  const src = readFileSync(path.join(REPO, file), "utf8");
  // Locate `export const <name>` and take the balanced object literal after `=`.
  const re = new RegExp(`export const ${exportName}[^=]*=\\s*`, "m");
  const m = re.exec(src);
  if (!m) throw new Error(`${exportName} not found in ${file}`);
  const start = src.indexOf("{", m.index + m[0].length - 1);
  let depth = 0, end = -1, inStr = null, prev = "";
  for (let i = start; i < src.length; i++) {
    const ch = src[i];
    if (inStr) {
      if (ch === inStr && prev !== "\\") inStr = null;
    } else if (ch === '"' || ch === "'" || ch === "`") {
      inStr = ch;
    } else if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) { end = i + 1; break; }
    }
    prev = ch;
  }
  if (end < 0) throw new Error(`unbalanced object literal for ${exportName} in ${file}`);
  const literal = src.slice(start, end);
  return vm.runInNewContext(`(${literal})`);
}

const out = {
  source: {
    repo: "csf-assessment",
    files: [
      "src/lib/assessment/guidance-deep.ts",
      "src/lib/assessment/guidance.data.ts",
      "src/lib/frameworks/csf-2.0-context.ts",
    ],
    note:
      "Authored guidance harvested from the csf-assessment web tool. Function `definition` " +
      "strings are NIST CSWP 29 text (public domain, 17 U.S.C. §105); `whyItMatters`, the " +
      "deep guidance, the function slants and the tier-transition paragraphs are original " +
      "authored content by Cyber Aware Creations.",
  },
  deepGuidance: extract("src/lib/assessment/guidance-deep.ts", "DEEP_GUIDANCE"),
  tierTransitions: extract("src/lib/assessment/guidance.data.ts", "TIER_TRANSITIONS"),
  functionSlants: extract("src/lib/assessment/guidance.data.ts", "FUNCTION_SLANTS"),
  tierNames: extract("src/lib/assessment/guidance.data.ts", "TIER_NAMES"),
  functionContext: extract("src/lib/frameworks/csf-2.0-context.ts", "FUNCTION_DEFINITIONS"),
};

// --- Integrity assertions: fail before writing ---
const problems = [];
const deepIds = Object.keys(out.deepGuidance);
if (deepIds.length !== 15) problems.push(`expected 15 deep-guidance entries, got ${deepIds.length}`);
for (const [id, e] of Object.entries(out.deepGuidance)) {
  if (!e.whatMatureLooksLike) problems.push(`${id}: missing whatMatureLooksLike`);
  if (!Array.isArray(e.nextSteps) || !e.nextSteps.length) problems.push(`${id}: missing nextSteps`);
}
for (const f of ["GV", "ID", "PR", "DE", "RS", "RC"]) {
  if (!out.functionSlants[f]) problems.push(`missing function slant for ${f}`);
  if (!out.functionContext[f]?.whyItMatters) problems.push(`missing whyItMatters for ${f}`);
}
for (const t of ["1", "2", "3"]) {
  if (!out.tierTransitions[t]) problems.push(`missing tier transition ${t}`);
}
if (problems.length) {
  console.error("HARVEST FAILED:");
  problems.forEach((p) => console.error("  - " + p));
  process.exit(1);
}

// The tool has no 0 level. The native scale does, so add the transition and label the
// skill needs for a Subcategory that is genuinely not started. Marked as ours, not
// harvested, so the provenance of every string stays traceable.
out.tierTransitions["0"] =
  "Moving from Not Implemented to Partial is about establishing the practice at all, in one " +
  "place, for one system or team — not about doing it well everywhere. Name an owner, pick " +
  "the narrowest scope that would still be meaningful, write down what you did, and accept " +
  "that it will be inconsistent. Consistency is the next step, not this one.";
out.tierNames["0"] = "Not Implemented";
out.added = {
  "tierTransitions.0": "Authored for this skill; the web tool had no 0 level.",
  "tierNames.0": "Authored for this skill; the web tool had no 0 level.",
};

writeFileSync(OUT, JSON.stringify(out, null, 2) + "\n");
console.log("OK");
console.log(`  deep guidance    ${deepIds.length} entries (${deepIds.join(", ")})`);
console.log(`  tier transitions ${Object.keys(out.tierTransitions).length} (incl. authored 0->1)`);
console.log(`  function slants  ${Object.keys(out.functionSlants).length}`);
console.log(`  function context ${Object.keys(out.functionContext).length}`);
console.log(`  -> ${OUT}`);
