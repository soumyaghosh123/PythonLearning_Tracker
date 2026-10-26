// Learning Tracker: Node run logger.
//
// setup.py adds `--require "<this file>"` to the user's NODE_OPTIONS, so Node
// loads this before every program. For scripts inside your code folder it
// records time, file, success / error / stopped, error type and duration, plus
// a snapshot of the code. Everything sits inside try/catch: it must never
// break your program, and it stays silent if hook.json is missing.
// To stop logging run: python tracker\setup.py --uninstall
try {
  const fs = require("fs");
  const path = require("path");
  const crypto = require("crypto");

  const cfg = JSON.parse(fs.readFileSync(process.env.JSTRACKER_HOOK_JSON || path.join(__dirname, "hook.json"), "utf8"));
  const script = path.resolve(process.argv[1]);
  const ext = path.extname(script).toLowerCase();
  const low = script.toLowerCase();
  const folder = path.resolve(cfg.code_folder).toLowerCase() + path.sep;
  const tracker = path.resolve(cfg.tracker_dir).toLowerCase() + path.sep;
  const tracked = [".js", ".mjs", ".cjs"].includes(ext) &&
    low.startsWith(folder) && !low.startsWith(tracker) &&
    !low.includes(path.sep + "node_modules" + path.sep);

  if (tracked) {
    const started = Date.now();
    let error = null;
    let stopped = false;

    const write = (code) => {
      try {
        const bytes = fs.readFileSync(script);
        const sha = crypto.createHash("sha256").update(bytes).digest("hex").slice(0, 16);
        const dir = path.join(cfg.data_dir, "javascript");
        const snaps = path.join(dir, "snapshots");
        fs.mkdirSync(snaps, { recursive: true });
        const snap = path.join(snaps, sha + ext);
        if (!fs.existsSync(snap)) fs.writeFileSync(snap, bytes);
        const failed = !!error || code !== 0;
        const entry = {
          time: new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 19),
          file: script,
          status: stopped ? "stopped" : (failed ? "error" : "success"),
          error: error || (code !== 0 && !stopped ? "exit code " + code : null),
          error_count: null,
          duration: Math.round((Date.now() - started) / 10) / 100,
          source: "hook",
          files: [{ file: script, sha: sha }],
        };
        fs.appendFileSync(path.join(dir, "runs.jsonl"), JSON.stringify(entry) + "\n");
      } catch (e) { /* never break the learner's program */ }
    };

    process.on("uncaughtExceptionMonitor", (e) => { error = (e && e.name) || "Error"; });
    process.once("SIGINT", () => {
      stopped = true;
      // Exit ourselves only when no learner handler is waiting to shut down gracefully.
      if (process.listenerCount("SIGINT") === 0) process.exit(130);
    });
    process.on("exit", (code) => write(code));
  }
} catch (e) { /* hook.json missing/unreadable or anything else: stay silent */ }
