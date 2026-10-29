// Run the exact production identity reader against bounded DOM fixtures.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../scripts/amazon_product_identity.py'), 'utf8');
const script = source.split('PRODUCT_IDENTITY_JS = r"""')[1].split('"""')[0];
function read(selected, canonical, rows=[], purchases=[], scripts=[]) {
  const document = {
    querySelector: selector => selector === '#ASIN' ? (selected ? {value:selected} : null) : (canonical ? {getAttribute:() => canonical} : null),
    querySelectorAll: selector => selector.includes('#addToCart') ? purchases.map(value => ({value}))
      : selector === '#twister_feature_div script' ? scripts.map(textContent => ({textContent}))
      : rows.map(textContent => ({textContent})),
  };
  return JSON.parse(JSON.stringify(vm.runInNewContext(`(${script})()`, {document})));
}
assert.deepEqual(read('B0DXPWV7XS', 'https://www.amazon.co.jp/dp/B0DXPWV7XS'), {
  selected_asin:'B0DXPWV7XS', canonical_url:'https://www.amazon.co.jp/dp/B0DXPWV7XS', detail_asins:[],
  purchase_asins:[], parent_relationship:null,
});
assert.deepEqual(read(null,null,['ASIN\n B00D3DV2BW', 'ASIN : B00D3DV2BW', 'ASIN\u200e : B08713SQHV', 'おすすめ ASIN B000000001']).detail_asins,
 ['B00D3DV2BW','B08713SQHV']);
assert.deepEqual(read(null,null), {selected_asin:'', canonical_url:'', detail_asins:[], purchase_asins:[], parent_relationship:null});
const child='B0BNH43W1M', parent='B0F42X5JXG', other='B0DNYN8VM3';
const moduleText = (data) => `P.register('twister-js-init-dpx-data', function() { var dataToReturn = ${JSON.stringify(data)}; return dataToReturn; });`;
const primary = moduleText({currentAsin:child,parentAsin:parent,nested:{parentAsin:parent}});
const observed = read(child, 'https://www.amazon.co.jp/dp/'+child, ['ASIN : '+parent], [child], [primary]);
assert.deepEqual(observed.parent_relationship, {source:'twister-js-init-dpx-data',current_asin:child,parent_asin:parent});
assert.deepEqual(observed.purchase_asins,[child]);
// Raw parent fields, recommendations, gallery metadata, mismatched and duplicate
// primary modules must never supply a trusted parent relationship.
for (const scripts of [
  [`var data = {"currentAsin":"${child}","parentAsin":"${parent}"};`],
  [primary.replace('twister-js-init-dpx-data','recommendations')],
  [primary.replace('twister-js-init-dpx-data','ImageBlockBTF')],
  [moduleText({currentAsin:child,parentAsin:parent,other:{parentAsin:other}})],
  [moduleText({currentAsin:child,parentAsin:parent,other:{currentAsin:other}})],
  [moduleText({parentAsin:parent})], [moduleText({currentAsin:child})],
  [primary,primary], [moduleText({currentAsin:child,parentAsin:'invalid'})],
]) {
  assert.equal(read(child,null,[],[child],scripts).parent_relationship,null);
}
assert.deepEqual(read(child,null,[],[child,'',other],[primary]).purchase_asins,[child,'',other]);
console.log('PASS production identity DOM: selected/canonical/details, purchase forms, trusted parent module, unrelated/ambiguous/missing metadata');
