// Level 9: Node
const fs = require("fs");
const http = require("http");
const chalk = require("chalk");
const test = require("node:test");
const assert = require("node:assert");

const file = process.argv[2] || "notes.txt";
const text = fs.readFileSync(file, "utf8");

test("file is not empty", () => {
  assert.ok(text.length > 0);
});

const server = http.createServer((req, res) => {
  res.end(chalk.green("ok"));
});
server.listen(3000);
