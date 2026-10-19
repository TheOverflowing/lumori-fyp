import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequestId } from '../app/static/request-id.js';

test('uses the native UUID method with its crypto receiver', () => {
  const crypto = { randomUUID() { assert.equal(this, crypto); return 'native-uuid'; } };
  assert.equal(createRequestId(crypto), 'native-uuid');
});

test('HTTP fallback preserves random bytes and sets UUID v4 version and variant', () => {
  let calls = 0;
  const crypto = { getRandomValues(bytes) { calls++; bytes.fill(255); return bytes; } };
  assert.equal(createRequestId(crypto), 'ffffffff-ffff-4fff-bfff-ffffffffffff');
  assert.equal(calls, 1);
});

test('does not substitute weak randomness if Web Crypto is unavailable', () => {
  assert.throws(() => createRequestId({}), TypeError);
});
