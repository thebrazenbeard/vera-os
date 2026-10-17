// Executable browser-script conformance without a guest or model.
// Run: node --test tests/test_cog_ui_literal_recovery.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '..', 'src', 'veraos', 'desktop.py'), 'utf8');
const match = html.match(/<script>\s*([\s\S]*?)\s*<\/script>/);
assert.ok(match, 'dashboard script must be parseable');

function boot({task, pending = null, failPost = false, postResult = null} = {}) {
  const conversation = 'console-' + 'a'.repeat(32);
  const backing = new Map([['veraos-local-conversation-v1', conversation]]);
  if (pending !== null) backing.set('veraos-local-pending-message-v1', JSON.stringify(pending));
  const storage = {
    getItem: key => backing.has(key) ? backing.get(key) : null,
    setItem: (key, value) => backing.set(key, value),
    removeItem: key => backing.delete(key),
  };
  const elems = {};
  function element(id) {
    return elems[id] ??= {
      value: id === 'message' ? task : '',
      textContent: '', disabled: false,
      addEventListener() {},
      replaceChildren() {},
    };
  }
  const requests = [];
  const ctx = vm.createContext({
    localStorage: storage,
    crypto: {getRandomValues: bytes => (bytes.fill(23), bytes)},
    Uint8Array,
    JSON, Array, encodeURIComponent,
    setInterval() {},
    document: {
      getElementById: element,
      createElement: tag => ({tag, textContent: ''}),
    },
    fetch: async (url, options = {}) => {
      requests.push({url, options});
      if (url === '/api/status') return {
        ok: true,
        json: async () => ({
          status: 'COMPOSED_NO_COGNITION',
          components: [], conversation_intake_available: true,
          canonical_runtime_qualified: false,
          cognition_route_qualified: false,
          protected_effect_authority: false,
        }),
      };
      if (url.startsWith('/api/conversation/history')) return {
        ok: true, json: async () => ({schema: 'VERAOS_CANONICAL_CONVERSATION_HISTORY_V1', messages: []}),
      };
      if (url === '/api/conversation') {
        if (failPost) throw new Error('simulated missing response');
        return {ok: true, json: async () => (postResult ?? {status: 'BLOCKED', task_id: 'ui-bound-task'})};
      }
      throw new Error('unexpected fetch ' + url);
    },
  });
  vm.runInContext(match[1], ctx, {timeout: 2500});
  return {
    ctx, elems, backing, requests, conversation,
    send: async () => {
      // Browser refresh is async; use deterministic source-only availability.
      vm.runInContext('conversationAvailable=true; sending=false;', ctx);
      await vm.runInContext('sendMessage()', ctx);
      return requests.filter(x => x.url === '/api/conversation');
    },
  };
}

test('invalid literal edge whitespace is REJECTED rather than silently normalized', async () => {
  const app = boot({task: '  original Î»  '});
  assert.equal((await app.send()).length, 0);
  assert.match(app.elems['conversation-result'].textContent, /INVALID|REJECTED|HELD/i);
});

test('valid original Unicode message is sent unchanged', async () => {
  const app = boot({task: 'Literal Î» user statement'});
  const posts = await app.send();
  assert.equal(posts.length, 1);
  assert.equal(JSON.parse(posts[0].options.body).task, 'Literal Î» user statement');
});

test('unresolved prior different literal blocks before minting another request ID', async () => {
  const c = 'console-' + 'a'.repeat(32);
  const app = boot({task: 'Different message',
    pending: {conversation_id: c, request_id: 'ui-previous', task: 'Prior unknown'}});
  assert.equal((await app.send()).length, 0);
  assert.equal(JSON.parse(app.backing.get('veraos-local-pending-message-v1')).request_id, 'ui-previous');
  assert.match(app.elems['conversation-result'].textContent, /UNKNOWN|HELD|BLOCKED/i);
});

test('canonical durable no-provider acknowledgment retires pending selector', async () => {
  const app = boot({task: 'Accepted task'});
  assert.equal((await app.send()).length, 1);
  assert.equal(app.backing.has('veraos-local-pending-message-v1'), false);
});

test('same literal with pending request retains exact request ID', async () => {
  const c = 'console-' + 'a'.repeat(32);
  const app = boot({task: 'Same text', pending: {
    conversation_id: c, request_id: 'ui-original', task: 'Same text'}});
  const posts = await app.send();
  assert.equal(posts.length, 1);
  assert.equal(JSON.parse(posts[0].options.body).request_id, 'ui-original');
});


test('lost HTTP response preserves exact unknown ID and blocks another text', async () => {
  const app = boot({task: 'Uncertain task', failPost: true});
  assert.equal((await app.send()).length, 1);
  const pending = JSON.parse(app.backing.get('veraos-local-pending-message-v1'));
  assert.equal(pending.task, 'Uncertain task');
  app.elems['message'].value = 'Different task';
  assert.equal((await app.send()).length, 1);
  assert.equal(JSON.parse(app.backing.get('veraos-local-pending-message-v1')).request_id,
               pending.request_id);
});

test('invalid cached pending JSON blocks before dispatch', async () => {
  const app = boot({task: 'Valid task'});
  app.backing.set('veraos-local-pending-message-v1', '{broken-json');
  assert.equal((await app.send()).length, 0);
  assert.equal(app.backing.get('veraos-local-pending-message-v1'), '{broken-json');
});

test('unattributable BLOCKED response does not erase pending original', async () => {
  const app = boot({task: 'Unproven', postResult: {status: 'BLOCKED'}});
  assert.equal((await app.send()).length, 1);
  assert.ok(app.backing.has('veraos-local-pending-message-v1'));
});
