// The one test of the consumer-matrix Node fixture (devkit #1762).
"use strict";

const assert = require("node:assert");
const fs = require("node:fs");
const test = require("node:test");
const { greet } = require("../index.js");

test("greet", () => {
  assert.strictEqual(greet("matrix"), "Hello, matrix!");
  // Proof for the matrix that `just test` really ran this suite.
  const sentinel = process.env.CONSUMER_MATRIX_SENTINEL;
  if (sentinel) {
    fs.writeFileSync(sentinel, "node\n");
  }
});
