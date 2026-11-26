// Runs every tests/js/*.test.mjs with Node's built-in test runner (`npm run test:js`).
//
// The files are listed here and passed by name because the runner's own directory and glob arguments differ
// between Node 20 (CI) and Node 22. One file is one process, which is also what lets each pick the Season or
// the Career page once.

import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const files = readdirSync(here)
  .filter((name) => name.endsWith(".test.mjs"))
  .sort()
  .map((name) => join(here, name));

const result = spawnSync(process.execPath, ["--no-warnings", "--test", ...files], { stdio: "inherit" });

process.exit(result.status ?? 1);
