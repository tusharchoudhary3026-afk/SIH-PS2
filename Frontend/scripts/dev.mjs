import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = path.resolve(frontendRoot, "..");
const apiUrl = process.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const apiEnv = {
  ...process.env,
  PYTHONPATH: [path.join(projectRoot, "src"), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
};
const apiCommand = process.platform === "win32" ? "py" : "python3";
const apiArgs = process.platform === "win32"
  ? ["-3", "-m", "engine8_api.server"]
  : ["-m", "engine8_api.server"];
const children = new Set();
let stopping = false;

function start(command, args, options) {
  const child = spawn(command, args, { stdio: "inherit", ...options });
  children.add(child);
  child.once("error", (error) => {
    console.error(`Could not start ${command}: ${error.message}`);
    stop(1);
  });
  child.once("close", (code) => {
    children.delete(child);
    if (!stopping) stop(code ?? 1);
  });
  return child;
}

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill();
  process.exitCode = code;
}

async function apiIsReady() {
  try {
    const response = await fetch(`${apiUrl}/api/health`, { signal: AbortSignal.timeout(700) });
    return response.ok && (await response.json()).status === "ok";
  } catch {
    return false;
  }
}

process.once("SIGINT", () => stop(0));
process.once("SIGTERM", () => stop(0));

let managedApi = null;
if (await apiIsReady()) {
  console.log(`Using the existing Engine 8 API at ${apiUrl}`);
} else {
  console.log("Starting the Engine 8 API...");
  managedApi = start(apiCommand, apiArgs, { cwd: projectRoot, env: apiEnv });
  let ready = false;
  for (let attempt = 0; attempt < 60 && !stopping; attempt += 1) {
    if (managedApi.exitCode !== null) break;
    if (await apiIsReady()) {
      ready = true;
      break;
    }
    await delay(250);
  }
  if (!ready) {
    console.error("Engine 8 did not become ready. Check the Python dependencies and port 8000.");
    stop(1);
  }
}

if (!stopping) {
  console.log("Starting the Vite frontend...");
  const viteCli = path.join(frontendRoot, "node_modules", "vite", "bin", "vite.js");
  start(process.execPath, [viteCli], { cwd: frontendRoot, env: process.env });
}
