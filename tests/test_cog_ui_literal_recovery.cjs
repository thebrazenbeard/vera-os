// Executable browser-script conformance without a guest or model.
// Run: node --test tests/test_cog_ui_literal_recovery.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {createHash, webcrypto} = require('node:crypto');
const digest = obj => createHash('sha256').update(JSON.stringify(obj)).digest('hex');

const html = fs.readFileSync(path.join(__dirname, '..', 'src', 'veraos', 'desktop.py'), 'utf8');
const match = html.match(/<script>\s*([\s\S]*?)\s*<\/script>/);
assert.ok(match, 'dashboard script must be parseable');

function boot({task, pending = null, failPost = false, postResult = null,
                postMutator = null, historyMutator = null, failHistory = false} = {}) {
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
  let historyRows = [];
  const ctx = vm.createContext({
    localStorage: storage,
    crypto: {getRandomValues: bytes => (bytes.fill(23), bytes), subtle: webcrypto.subtle},
    Uint8Array, TextEncoder,
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
      if (url.startsWith('/api/conversation/history')) {
        const data = {schema: 'VERAOS_CANONICAL_CONVERSATION_HISTORY_V1',
          conversation_id: conversation, messages: historyRows,
          truncated: false, memory_admitted: false, model_admitted: false};
        return {ok: !failHistory, json: async () => (
          historyMutator ? historyMutator(data) : data)};
      }
      if (url === '/api/conversation') {
        if (failPost) throw new Error('simulated missing response');
        const msg = JSON.parse(options.body);
        const taskId = 'ui-' + digest({conversation_id: msg.conversation_id,
          message_id: msg.request_id, schema: 'VERAOS_LOCAL_MESSAGE_KEY_V1'});
        const sourceDigest = digest({conversation_id: msg.conversation_id,
          message_id: msg.request_id, schema: 'VERAOS_LOCAL_UI_INTAKE_SOURCE_V1',
          text: msg.task});
        const opened = 'a'.repeat(64);
        const canonical = {schema: 'VERAOS_CANONICAL_NO_PROVIDER_ACK_V1',
          conversation_id: msg.conversation_id, message_id: msg.request_id,
          text: msg.task, task_id: taskId, source_digest: sourceDigest,
          opened_head: opened, task_journal_head: opened,
          canonical_status: 'PENDING_NO_ADMITTED_PROVIDER', origin_authenticated: false};
        historyRows = [{conversation_id: msg.conversation_id,
          message_id: msg.request_id, text: msg.task, task_id: taskId,
          source_digest: sourceDigest, task_journal_head: opened,
          status: 'PENDING_NO_ADMITTED_PROVIDER', source_kind: 'UNTRUSTED_USER_INPUT',
          accepted_as_task_result: false, memory_admitted: false}];
        const normal = {status: 'BLOCKED', task_id: taskId, canonical_intake: canonical};
        return {ok: true, json: async () => (postResult ?? (
          postMutator ? postMutator(normal) : normal))};
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


test('forged BLOCKED/ui identifier cannot retire the pending original', async () => {
  const app = boot({task:'Forged', postResult:{status:'BLOCKED',task_id:'ui-fabricated-no-source-proof'}});
  assert.equal((await app.send()).length,1);
  assert.ok(app.backing.has('veraos-local-pending-message-v1'));
  assert.match(app.elems['conversation-result'].textContent,/UNKNOWN|unverified/i);
});

test('POST wrong conversation/message/literal/source/head cannot clear', async () => {
  const mutants = [
    p=>({...p, canonical_intake:{...p.canonical_intake,conversation_id:'console-other'}}),
    p=>({...p, canonical_intake:{...p.canonical_intake,message_id:'ui-other'}}),
    p=>({...p, canonical_intake:{...p.canonical_intake,text:'Other literal'}}),
    p=>({...p, canonical_intake:{...p.canonical_intake,source_digest:'e'.repeat(64)}}),
    p=>({...p, canonical_intake:{...p.canonical_intake,opened_head:'f'.repeat(64)}}),
    p=>({...p, task_id:'ui-'+'f'.repeat(64)}),
  ];
  for(const postMutator of mutants){
    const app=boot({task:'Exact source',postMutator});
    assert.equal((await app.send()).length,1);
    assert.ok(app.backing.has('veraos-local-pending-message-v1'));
  }
});

test('stale, missing or contradictory read-only Mono history keeps original ID', async () => {
  const hostile = [
    d=>({...d,messages:[]}),
    d=>({...d,messages:[{...d.messages[0],task_journal_head:'f'.repeat(64)}]}),
    d=>({...d,messages:[{...d.messages[0],text:'substitution'}]}),
    d=>({...d,messages:[{...d.messages[0],status:'SOURCE_COMPLETED_UNSEALED_NO_REDISPATCH'}]}),
    d=>({...d,messages:[...d.messages,d.messages[0]]}),
    d=>({...d,truncated:true}),
  ];
  for(const historyMutator of hostile){
    const app=boot({task:'Original',historyMutator});
    assert.equal((await app.send()).length,1);
    assert.ok(app.backing.has('veraos-local-pending-message-v1'));
  }
  const missing = boot({task:'History down',failHistory:true});
  assert.equal((await missing.send()).length,1);
  assert.ok(missing.backing.has('veraos-local-pending-message-v1'));
});

test('unqualified synthetic fixture result cannot retire canonical pending ID', async () => {
  const app=boot({task:'Only a fixture',postResult:{
    status:'COMPLETED',synthetic:true,final_text:'simulated'}});
  vm.runInContext('syntheticFixture=true;',app.ctx);
  assert.equal((await app.send()).length,1);
  assert.ok(app.backing.has('veraos-local-pending-message-v1'));
});

test('history.truncated MUST be explicitly false before canonical pending retirement', async () => {
  const hostileValues = [
    ['missing', d => { const h={...d}; delete h.truncated; return h; }],
    ['string-false', d => ({...d,truncated:'false'})],
    ['string-true', d => ({...d,truncated:'true'})],
    ['null', d => ({...d,truncated:null})],
    ['zero', d => ({...d,truncated:0})],
    ['object', d => ({...d,truncated:{value:false}})],
    ['array', d => ({...d,truncated:[]})],
    ['boolean-true', d => ({...d,truncated:true})],
  ];
  for(const [name,historyMutator] of hostileValues){
    const app=boot({task:'Original unchanged literal',historyMutator});
    const first=await app.send();
    assert.equal(first.length,1,name+' first intake');
    const original=JSON.parse(app.backing.get('veraos-local-pending-message-v1'));
    assert.equal(original.task,'Original unchanged literal',name);
    assert.match(app.elems['conversation-result'].textContent,/UNKNOWN|unverified/i,name);
    // An unacknowledged original cannot be silently replaced by another
    // conversation message and must not produce a new request identity.
    app.elems['message'].value='Different user text';
    const after=await app.send();
    assert.equal(after.length,1,name+' no second dispatch');
    assert.equal(JSON.parse(app.backing.get('veraos-local-pending-message-v1')).request_id,
                 original.request_id,name+' exact replay selector');
  }
});
