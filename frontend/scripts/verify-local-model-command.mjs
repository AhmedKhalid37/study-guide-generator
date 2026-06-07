// Unit harness for the Local Models command-helper pure helpers (LMM Slice 4).
//
// Mirrors verify-local-model-status.mjs (plain node, no test runner, no new dep).
// Imports the REAL src/localModelCommand.js — pure ESM, no React/JSX. Run:
//
//   node scripts/verify-local-model-command.mjs
//
// Proves: profile normalization (drops command-less/garbage), default + by-id
// selection, copy-availability gating, deterministic command string (placeholder
// path + host/port), warnings/notes pass-through, copy-button label states, and
// graceful degradation when the command-profile data is missing.

import {
  COPY_COPIED,
  COPY_FAILED,
  COPY_IDLE,
  commandAvailable,
  commandNotes,
  commandProfiles,
  copyButtonLabel,
  defaultProfile,
  normalizeProfile,
  profileById,
} from "../src/localModelCommand.js";

let failed = 0;
function check(name, cond, detail = "") {
  if (cond) {
    console.log(`✓ ${name}`);
  } else {
    console.error(`✗ ${name}${detail ? ` — ${detail}` : ""}`);
    failed += 1;
  }
}

// DTO mirroring pipeline/provider_config.get_local_model_command_profiles.
const data = {
  ok: true,
  provider: "local",
  in_docker: true,
  base_url_host: "host.docker.internal",
  profile: {
    id: "llama_server_cpu_safe",
    label: "CPU safe",
    description: "CPU-only safe default.",
    command:
      "llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8080 -c 4096 -ngl 0 --threads 8",
    argv: [
      "llama-server", "-m", "/path/to/model.gguf", "--host", "0.0.0.0",
      "--port", "8080", "-c", "4096", "-ngl", "0", "--threads", "8",
    ],
    placeholders: { model_path: "/path/to/model.gguf" },
    warnings: ["Edit the model path before running.", "Run this on your host machine."],
  },
  profiles: [
    {
      id: "llama_server_cpu_safe",
      label: "CPU safe",
      command:
        "llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8080 -c 4096 -ngl 0 --threads 8",
      argv: ["llama-server", "-m", "/path/to/model.gguf"],
      warnings: ["Edit the model path before running."],
    },
    {
      id: "llama_server_gpu_balanced",
      label: "GPU balanced",
      command: "llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8080 -c 4096 -ngl 20 --threads 8",
      argv: ["llama-server", "-m", "/path/to/model.gguf"],
      warnings: [],
    },
    {
      id: "llama_server_low_memory",
      label: "Low memory",
      command: "llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8080 -c 2048 -ngl 0 --threads 8",
      argv: ["llama-server", "-m", "/path/to/model.gguf"],
      warnings: [],
    },
    {
      id: "llama_server_full_offload_risky",
      label: "Advanced full offload (risky / may OOM)",
      command: "llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8080 -c 4096 -ngl 999 --threads 8",
      argv: ["llama-server", "-m", "/path/to/model.gguf"],
      warnings: [],
    },
  ],
  notes: ["The app does not start, stop, or run llama-server.", "Point base URL at the host."],
};

// ── normalization ────────────────────────────────────────────────────────────
check("normalizeProfile keeps a valid profile", normalizeProfile(data.profile) !== null);
check("normalizeProfile drops null", normalizeProfile(null) === null);
check("normalizeProfile drops non-object", normalizeProfile("nope") === null);
check("normalizeProfile drops command-less profile", normalizeProfile({ id: "x", command: "" }) === null);
check("normalizeProfile drops whitespace-only command", normalizeProfile({ id: "x", command: "   " }) === null);
check(
  "normalizeProfile fills label from id when missing",
  normalizeProfile({ id: "abc", command: "run" }).label === "abc"
);
check(
  "normalizeProfile defaults arrays/objects safely",
  (() => {
    const p = normalizeProfile({ id: "x", command: "run" });
    return Array.isArray(p.argv) && Array.isArray(p.warnings) && typeof p.placeholders === "object";
  })()
);

// ── profiles list + selection ─────────────────────────────────────────────────
check("commandProfiles returns all usable profiles", commandProfiles(data).length === 4);
check("commandProfiles tolerates missing", commandProfiles({}).length === 0);
check(
  "commandProfiles drops garbage entries",
  commandProfiles({ profiles: [null, { id: "ok", command: "run" }, { id: "no-cmd" }] }).length === 1
);
check("defaultProfile prefers the DTO profile", defaultProfile(data).id === "llama_server_cpu_safe");
check(
  "defaultProfile falls back to first usable when profile missing",
  defaultProfile({ profiles: data.profiles }).id === "llama_server_cpu_safe"
);
check("defaultProfile is null when nothing usable", defaultProfile({}) === null);
check("profileById resolves the balanced GPU profile", profileById(data, "llama_server_gpu_balanced").id === "llama_server_gpu_balanced");
check("profileById falls back to default on unknown id", profileById(data, "nope").id === "llama_server_cpu_safe");
check("profileById falls back to default on null id", profileById(data, null).id === "llama_server_cpu_safe");

// ── copy availability gating ──────────────────────────────────────────────────
check("commandAvailable true for a real profile", commandAvailable(defaultProfile(data)) === true);
check("commandAvailable false for null", commandAvailable(null) === false);
check("commandAvailable false for empty command", commandAvailable({ command: "" }) === false);
check("commandAvailable false when data missing (graceful)", commandAvailable(defaultProfile({})) === false);

// ── deterministic command content ─────────────────────────────────────────────
const cmd = defaultProfile(data).command;
check("command contains the placeholder model path", cmd.includes("/path/to/model.gguf"));
check("command contains --host 0.0.0.0", cmd.includes("--host 0.0.0.0"));
check("command contains --port 8080", cmd.includes("--port 8080"));
check("command contains CPU-safe gpu layers", cmd.includes("-ngl 0"));
check("command contains --threads 8", cmd.includes("--threads 8"));
check("command starts with llama-server", cmd.startsWith("llama-server "));
check("default command does not use full offload", !/(--n-gpu-layers|-ngl)\s+999/.test(cmd));
check("CPU safe preset exists", commandProfiles(data).some((p) => p.label === "CPU safe" && /-ngl\s+0/.test(p.command)));
check("GPU balanced preset exists", commandProfiles(data).some((p) => p.label === "GPU balanced" && /-ngl\s+20/.test(p.command)));
check("low-memory preset exists", commandProfiles(data).some((p) => p.label === "Low memory" && /-c\s+2048/.test(p.command)));
check("full offload option is explicit risky and not default", commandProfiles(data).some((p) => /risky \/ may OOM/.test(p.label) && /-ngl\s+999/.test(p.command)) && defaultProfile(data).id !== "llama_server_full_offload_risky");
check(
  "command is deterministic (same DTO → same string)",
  defaultProfile(data).command === defaultProfile(data).command
);

// ── warnings + notes pass-through ─────────────────────────────────────────────
check("warnings passed through", defaultProfile(data).warnings.length === 2);
check("warnings filter non-strings", normalizeProfile({ id: "x", command: "run", warnings: ["a", 1, null] }).warnings.length === 1);
check("commandNotes returns the notes array", commandNotes(data).length === 2);
check("commandNotes tolerates missing", commandNotes({}).length === 0);
check("commandNotes tolerates non-array", commandNotes({ notes: "x" }).length === 0);

// ── copy button label states ──────────────────────────────────────────────────
check("copy label idle", copyButtonLabel(COPY_IDLE) === "Copy command");
check("copy label copied", copyButtonLabel(COPY_COPIED) === "Copied");
check("copy label failed is a manual-copy instruction", /manually/.test(copyButtonLabel(COPY_FAILED)));
check("copy label default for unknown state", copyButtonLabel("???") === "Copy command");

// ── invariant: no execute/start affordance in this module ─────────────────────
import * as mod from "../src/localModelCommand.js";
check(
  "module exposes NO execute/start/spawn/run helper (copy-only)",
  !Object.keys(mod).some((k) => /^(execute|start|spawn|run|launch|stop)/i.test(k)),
  Object.keys(mod).join(",")
);

if (failed) {
  console.error(`\n${failed} local-model-command check(s) failed.`);
  process.exit(1);
}
console.log("\nAll local-model-command checks passed.");
