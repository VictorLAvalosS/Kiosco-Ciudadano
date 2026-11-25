#!/usr/bin/env node
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");
const backendDir = path.resolve(rootDir, "backend");

// Buscar el intérprete del entorno virtual o el del sistema
const candidates = [
  path.join(backendDir, ".venv", "bin", "python"),
  path.join(backendDir, ".venv", "bin", "python3"),
  path.join(backendDir, ".venv", "Scripts", "python.exe"),
  path.join(backendDir, ".venv", "Scripts", "python"),
];

let pythonBin = candidates.find((p) => fs.existsSync(p));
if (!pythonBin) {
  pythonBin = process.platform === "win32" ? "python" : "python3";
}

const args = process.argv.slice(2);
const child = spawn(pythonBin, args, {
  cwd: backendDir,
  stdio: "inherit",
  shell: process.platform === "win32",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
  } else {
    process.exit(code ?? 0);
  }
});
