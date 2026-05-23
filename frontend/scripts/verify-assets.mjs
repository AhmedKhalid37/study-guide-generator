import { accessSync, readFileSync } from "node:fs";
import { join } from "node:path";

const requiredFiles = [
  "public/mockups/mobile-welcome.png",
  "public/mockups/mobile-home.png",
  "public/mockups/mobile-exam-cram.png",
  "public/mockups/mobile-claude-style.png",
  "public/mockups/desktop-dashboard.png",
  "src/components/TopBar.jsx",
  "src/components/FallbackImage.jsx",
  "src/App.jsx"
];

let failed = false;
for (const file of requiredFiles) {
  try {
    accessSync(join(process.cwd(), file));
    console.log(`✓ ${file}`);
  } catch {
    console.error(`✗ Missing: ${file}`);
    failed = true;
  }
}

const app = readFileSync(join(process.cwd(), "src/App.jsx"), "utf8");
const requiredSnippets = ["<TopBar", "<PhoneMockup", "<DesktopMockup", "view === \"mobile\"", "view === \"desktop\"", "view === \"all\""];
for (const snippet of requiredSnippets) {
  if (app.includes(snippet)) {
    console.log(`✓ App contains ${snippet}`);
  } else {
    console.error(`✗ App missing ${snippet}`);
    failed = true;
  }
}

if (failed) process.exit(1);
console.log("All UI asset checks passed.");
