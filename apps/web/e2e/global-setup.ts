import { execFileSync } from "child_process";
import path from "path";

/** Re-seed (idempotent) so the demo calendar is anchored to today and demo rooms are reset. */
export default async function globalSetup() {
  const apiDir = path.resolve(__dirname, "..", "..", "api");
  const python = path.join(apiDir, "venv", "Scripts", "python.exe");
  execFileSync(python, [path.join(apiDir, "seed", "run_seed.py")], { cwd: apiDir, stdio: "inherit" });
}
