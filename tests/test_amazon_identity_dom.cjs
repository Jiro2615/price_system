// Run the exact production identity reader against bounded DOM fixtures.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../scripts/amazon_product_identity.py'), 'utf8');
const script = source.split('PRODUCT_IDENTITY_JS = r"""')[1].split('"""')[0];
function read(selected, canonical, rows=[]) {
  const document = {
    querySelector: selector => selector === '#ASIN' ? (selected ? {value:selected} : null) : (canonical ? {getAttribute:() => canonical} : null),
    querySelectorAll: () => rows.map(textContent => ({textContent})),
  };
  return JSON.parse(JSON.stringify(vm.runInNewContext(`(${script})()`, {document})));
}
assert.deepEqual(read('B0DXPWV7XS', 'https://www.amazon.co.jp/dp/B0DXPWV7XS'), {
  selected_asin:'B0DXPWV7XS', canonical_url:'https://www.amazon.co.jp/dp/B0DXPWV7XS', detail_asins:[],
});
assert.deepEqual(read(null,null,['ASIN\n B00D3DV2BW', 'ASIN : B00D3DV2BW', 'ASIN\u200e : B08713SQHV', 'おすすめ ASIN B000000001']).detail_asins,
 ['B00D3DV2BW','B08713SQHV']);
assert.deepEqual(read(null,null), {selected_asin:'', canonical_url:'', detail_asins:[]});
console.log('PASS production identity DOM: selected product, canonical, details, duplicate/irrelevant text, missing identity');
