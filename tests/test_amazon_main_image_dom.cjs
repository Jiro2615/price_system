// Run the exact production DOM expression against small product fixtures.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../scripts/price_check_one_asin_db.py'), 'utf8');
const start = source.indexOf('candidates = await page.evaluate("""asin => {');
assert.ok(start >= 0);
const expression = source.slice(start + 'candidates = await page.evaluate("""'.length, source.indexOf('""", asin)', start));
function run(image, asin='B000000001') {
  const calls = [];
  const ctx = vm.createContext({document: {querySelector(selector) {
    calls.push(selector);
    return selector === '#ASIN' ? {value: asin} : image;
  }}});
  const output = vm.runInContext(`(${expression})('B000000001')`, ctx);
  return {output: Array.from(output), calls};
}
const url = key => `https://m.media-amazon.com/images/I/${key}.jpg`;
let {output, calls} = run({getAttribute: key => key === 'data-old-hires' ? url('high') : JSON.stringify({[url('small')]: [100,100], [url('big')]: [1200,1200]}), currentSrc: url('current'), src: url('src')});
assert.deepEqual(output, [url('high'), url('big'), url('small'), url('current'), url('src')]);
assert.ok(calls[1].includes('#imgBlkFront'));
assert.ok(calls[1].includes('#ebooksImgBlkFront'));
assert.deepEqual(run(null).output, []);
assert.deepEqual(run({getAttribute: () => {throw Error('must not read wrong ASIN');}}, 'B000000002').output, []);
output = run({getAttribute: () => 'broken JSON', currentSrc: url('current'), src: url('src')}).output;
assert.equal(output.at(-2), url('current'));
console.log('PASS selected main image DOM, high-resolution order, book selectors, missing/wrong ASIN and malformed metadata');
