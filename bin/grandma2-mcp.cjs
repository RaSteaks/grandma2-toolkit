#!/usr/bin/env node
const { spawn } = require("node:child_process")
const { homedir } = require("node:os")
const path = require("node:path")

// Resolve the Python project from the installed package, even when the MCP host
// starts in another directory. Keep evidence outside npx's disposable cache.
const project = path.resolve(__dirname, "..")
const child = spawn("uv", [
  "run", "--locked", "--no-dev", "--project", project,
  "python", "-m", "grandma2_toolkit.server",
], {
  stdio: "inherit",
  env: {
    ...process.env,
    MA2_OUTPUT_DIR: process.env.MA2_OUTPUT_DIR || path.join(homedir(), ".grandma2-toolkit", ".data"),
  },
})

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal))
}
child.on("error", (error) => {
  console.error(error.code === "ENOENT" ? "grandma2-mcp: install uv and add it to PATH." : error.message)
  process.exitCode = 1
})
child.on("exit", (code, signal) => {
  process.exitCode = code ?? (signal === "SIGINT" ? 130 : 143)
})
