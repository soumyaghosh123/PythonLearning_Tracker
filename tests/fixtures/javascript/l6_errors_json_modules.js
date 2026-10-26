// Level 6: errors, JSON, modules
import { readFileSync } from "node:fs";
import helper from "./helper.js";
const legacy = require("./legacy");

export function parseConfig(text) {
  try {
    return JSON.parse(text);
  } catch (err) {
    throw new Error("Bad config: " + err.message);
  }
}

export const saved = JSON.stringify({ ok: true });
console.log(readFileSync, helper, legacy, saved);
