import test from 'node:test';
import assert from 'node:assert/strict';
import { beginRouteFocus } from '../app/static/route-focus.js';

const previous = {account:'teacher-a', course:'ml', route:'contents', id:''};
const next = {...previous, route:'content', id:'material-a'};

function fixture({from = previous, to = next, headingLevel = 'h1'} = {}) {
  const listeners = new Map(), attributes = new Map(), controller = new AbortController();
  const heading = {focuses:[],
    hasAttribute:name => attributes.has(name),
    setAttribute:(name, value) => attributes.set(name, value),
    focus(options) { this.focuses.push(options); },
  };
  const root = {isConnected:true, querySelector:selector => selector === headingLevel ? heading : null};
  const window = {
    addEventListener(name, fn) { if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name).add(fn); },
    removeEventListener(name, fn) { listeners.get(name)?.delete(fn); },
  };
  return {heading, root, attributes, controller,
    input:event => { for (const fn of listeners.get(event) || []) fn(); },
    listenerCount:() => [...listeners.values()].reduce((n, values) => n + values.size, 0),
    focus:beginRouteFocus({root, previous:from, next:to, signal:controller.signal, window}),
  };
}

test('arriving at a different material focuses its title without changing scroll position or tab order', () => {
  const f = fixture({from:{...next, id:'material-before'}});
  assert.equal(f.focus.finish(), true);
  assert.deepEqual(f.heading.focuses, [{preventScroll:true}]);
  assert.equal(f.attributes.get('tabindex'), '-1');
  assert.equal(f.listenerCount(), 0);
  assert.equal(f.focus.finish(), false);
  assert.equal(f.heading.focuses.length, 1);
});

test('initial bootstrap, account replacement and unchanged route refresh leave focus alone', () => {
  for (const from of [null, {...next}, {...previous, account:'teacher-b'}]) {
    const f = fixture({from});
    assert.equal(f.focus.finish(), false);
    assert.deepEqual(f.heading.focuses, []);
    assert.equal(f.listenerCount(), 0);
  }
});

test('changing courses announces the new page while a restored list keeps its saved focus', () => {
  const course = fixture({to:{...previous, course:'algorithms'}});
  assert.equal(course.focus.finish(), true);
  const restored = fixture({from:next, to:previous});
  assert.equal(restored.focus.finish({restored:true}), false);
  assert.deepEqual(restored.heading.focuses, []);
  assert.equal(restored.listenerCount(), 0);
});

test('input during a pending navigation prevents a late focus jump', () => {
  for (const event of ['keydown', 'pointerdown', 'touchstart', 'wheel']) {
    const f = fixture();
    f.input(event);
    assert.equal(f.focus.finish(), false);
    assert.deepEqual(f.heading.focuses, []);
    assert.equal(f.listenerCount(), 0);
  }
});

test('superseding the request releases listeners and cannot focus an obsolete response', () => {
  const f = fixture();
  f.controller.abort();
  assert.equal(f.listenerCount(), 0);
  assert.equal(f.focus.finish(), false);
  assert.deepEqual(f.heading.focuses, []);
});

test('failed navigation announces the error heading and preserves an existing tabindex', () => {
  const f = fixture({headingLevel:'h2'});
  f.attributes.set('tabindex', '0');
  assert.equal(f.focus.finish(), true);
  assert.deepEqual(f.heading.focuses, [{preventScroll:true}]);
  assert.equal(f.attributes.get('tabindex'), '0');
});

test('disconnected pages and pages without headings do not create invalid focus targets', () => {
  const detached = fixture();
  detached.root.isConnected = false;
  assert.equal(detached.focus.finish(), false);
  const empty = fixture({headingLevel:null});
  assert.equal(empty.focus.finish(), false);
  assert.equal(empty.listenerCount(), 0);
});
