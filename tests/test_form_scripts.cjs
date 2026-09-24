const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const base = path.join(__dirname, '../frappe_hr_pph21/frappe_hr_pph21/doctype');
function harness(slug) {
  const handlers = {}, locals = {}, pending = [];
  const frappe = {
    ui: { form: { on: (dt, obj) => handlers[dt] = obj } },
    datetime: { get_today: () => '2026-09-23' },
    call: () => new Promise(resolve => pending.push(resolve)),
    model: { set_value: async (dt, name, values) => Object.assign(locals[dt][name], values) },
  };
  vm.runInNewContext(fs.readFileSync(path.join(base, slug, slug + '.js'), 'utf8'), { frappe, locals, __: x => x });
  return { handlers, locals, pending };
}
const tick = () => new Promise(resolve => setImmediate(resolve));
test('account queries follow company, type, currency and leaf/active flags', async () => {
  const {handlers} = harness('pph21_settings');
  const queries = {};
  const frm = { doc: {company: 'A',expense_account:'OLD',tax_payable_account:'OLD'},
    set_query: (f, a, b) => queries[f] = b || a,
    set_value: async values => Object.assign(frm.doc, values) };
  handlers['PPh21 Settings'].setup(frm);
  assert.equal(queries.expense_account().filters.company,'A');
  assert.equal(queries.expense_account().filters.root_type,'Expense');
  assert.equal(queries.tax_payable_account().filters.root_type,'Liability');
  assert.equal(queries.expense_account().filters.account_currency,'IDR');
  assert.equal(queries.expense_account().filters.is_group,0);
  assert.equal(queries.expense_account().filters.disabled,0);
  frm.doc.company='B';
  await handlers['PPh21 Settings'].company(frm);
  assert.equal(queries.expense_account().filters.company,'B');
  assert.equal(frm.doc.expense_account,null);
  assert.equal(frm.doc.tax_payable_account,null);
  assert.equal(queries.salary_component().query,'frappe_hr_pph21.queries.salary_component_query');
});
test('bulk new rows inherit defaults without overwriting existing rows', async () => {
  const h = harness('bulk_pph21_employee_tax_profile');
  const dt='Bulk PPh21 Employee Tax Profile Row';
  h.locals[dt]={r:{}};
  h.handlers[dt].employees_add({doc:{default_fiscal_year:'FY-2025',default_method:'Gross'}},dt,'r');
  await tick();
  assert.equal(h.locals[dt].r.fiscal_year,'FY-2025');
  assert.equal(h.locals[dt].r.method,'Gross');
});
test('bulk employee changes clear stale identity and load defaults', async () => {
  const h=harness('bulk_pph21_employee_tax_profile');
  const dt='Bulk PPh21 Employee Tax Profile Row';
  h.locals[dt]={r:{employee:'A',company:'Old',tax_id:'old-id',ptkp_status:'K/3',pph21_settings:'Old setting'}};
  const action=h.handlers[dt].employee({},dt,'r'); await tick();
  assert.equal(h.locals[dt].r.tax_id,'');
  assert.equal(h.locals[dt].r.pph21_settings,null);
  h.pending[0]({message:{company:'Company A',employee_name:'Alice',ptkp_status:'TK/0'}});
  await action;
  assert.equal(h.locals[dt].r.company,'Company A');
  assert.equal(h.locals[dt].r.ptkp_status,'TK/0');
});
test('late employee lookup cannot overwrite a different employee', async () => {
  const h=harness('bulk_pph21_employee_tax_profile');
  const dt='Bulk PPh21 Employee Tax Profile Row';
  h.locals[dt]={r:{employee:'A'}};
  const a=h.handlers[dt].employee({},dt,'r'); await tick();
  h.locals[dt].r.employee='B';
  const b=h.handlers[dt].employee({},dt,'r'); await tick();
  h.pending[1]({message:{company:'B Co',employee_name:'Bob',ptkp_status:'K/1'}}); await b;
  h.pending[0]({message:{company:'A Co',employee_name:'Alice',ptkp_status:'TK/0'}}); await a;
  assert.equal(h.locals[dt].r.company,'B Co');
  assert.equal(h.locals[dt].r.ptkp_status,'K/1');
});
test('manual PTKP selected during lookup is preserved', async () => {
  const h=harness('bulk_pph21_employee_tax_profile');
  const dt='Bulk PPh21 Employee Tax Profile Row'; h.locals[dt]={r:{employee:'A'}};
  const a=h.handlers[dt].employee({},dt,'r'); await tick();
  h.locals[dt].r.ptkp_status='TK/2';
  h.pending[0]({message:{company:'A',employee_name:'Alice',ptkp_status:'TK/0'}}); await a;
  assert.equal(h.locals[dt].r.ptkp_status,'TK/2');
});
test('individual profile loads Employee defaults and resets previous identity', async () => {
  const h=harness('pph21_employee_tax_profile');
  const frm={doc:{employee:'A',tax_id:'old',ptkp_status:'K/3'},set_value:async (key,val)=> {
    if (typeof key==='object') Object.assign(frm.doc,key); else frm.doc[key]=val;
  }};
  const handler=h.handlers['PPh21 Employee Tax Profile'];
  const a=handler.employee(frm); await tick();
  h.pending[0]({message:{company:'A Co',employee_name:'Alice',ptkp_status:'TK/0'}}); await a;
  await handler.ptkp_status(frm);
  assert.equal(frm.doc.company,'A Co');
  assert.equal(frm.doc.tax_id,'');
  assert.equal(frm.doc.ter_category,'A');
});
test('Fiscal Year links use master records on individual and bulk forms', () => {
  for (const [slug,doctype,expected] of [
    ['pph21_employee_tax_profile','PPh21 Employee Tax Profile',['fiscal_year']],
    ['bulk_pph21_employee_tax_profile','Bulk PPh21 Employee Tax Profile',['default_fiscal_year','fiscal_year']],
  ]) {
    const h=harness(slug), queries={};
    h.handlers[doctype].setup({set_query:(name,a,b)=>queries[name]=b||a});
    for (const name of expected) assert.equal(queries[name]().filters.disabled,0);
  }
});

test('settings links follow employee company on individual and bulk profiles', async () => {
  const h=harness('pph21_employee_tax_profile'), queries={};
  const frm={doc:{company:'A'},set_query:(field,a,b)=>queries[field]=b||a};
  h.handlers['PPh21 Employee Tax Profile'].setup(frm);
  assert.equal(queries.pph21_settings().filters.company,'A');
  assert.equal(queries.pph21_settings().filters.enabled,1);
  frm.doc.company='B';assert.equal(queries.pph21_settings().filters.company,'B');
  const bulk=harness('bulk_pph21_employee_tax_profile'), bq={},dt='Bulk PPh21 Employee Tax Profile Row';
  bulk.locals[dt]={one:{company:'A'},two:{company:'B'}};
  bulk.handlers['Bulk PPh21 Employee Tax Profile'].setup({set_query:(field,a,b)=>bq[field]=b||a});
  assert.equal(bq.pph21_settings({},dt,'one').filters.company,'A');
  assert.equal(bq.pph21_settings({},dt,'two').filters.company,'B');
});
