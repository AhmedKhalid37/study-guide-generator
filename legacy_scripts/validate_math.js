#!/usr/bin/env node
const fs = require("fs");
const katex = require("katex");

const file = process.argv[2];
const showMath = process.argv.includes("--show-math");

if (!file) {
  console.error("Usage: node scripts/validate_math.js file.md [--show-math]");
  process.exit(1);
}

let text = fs.readFileSync(file, "utf8");

// Protect escaped dollars so they do not look like math delimiters.
text = text.replace(/\\\$/g, "ESCAPED_DOLLAR");

const errors = [];

function validate(expr, displayMode, index) {
  if (showMath) {
    console.log(`[${displayMode ? "display" : "inline"} ${index}] ${expr}`);
  }
  try {
    katex.renderToString(expr, {
      throwOnError: true,
      displayMode,
      strict: false
    });
  } catch (e) {
    errors.push({ expr, displayMode, error: e.message });
  }
}

// Display math: $$ ... $$
let displayIndex = 0;
text = text.replace(/\$\$([\s\S]*?)\$\$/g, (m, expr) => {
  validate(expr.trim(), true, displayIndex++);
  return "DISPLAY_MATH_BLOCK";
});

// Inline math: $ ... $
let inlineIndex = 0;
const inlineRe = /(^|[^\\])\$([^\n$]+?)\$/g;
let match;
while ((match = inlineRe.exec(text)) !== null) {
  validate(match[2].trim(), false, inlineIndex++);
}

if (errors.length > 0) {
  console.error(`Math validation failed: ${errors.length} error(s)\n`);
  errors.forEach((e, i) => {
    console.error(`#${i + 1} ${e.displayMode ? "display" : "inline"}`);
    console.error(e.expr);
    console.error(e.error);
    console.error("");
  });
  process.exit(1);
}

console.log(`Math validation passed. Display blocks: ${displayIndex}, inline formulas: ${inlineIndex}`);
