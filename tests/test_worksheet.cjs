const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const escape_html = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fixture = name => JSON.parse(fs.readFileSync(path.join(__dirname,`fixtures/worksheet_${name}.json`),'utf8'));
function harness() {
    const handlers = {}, dialogs = [];
    const wrap = () => ({value:'', html(v){this.value=v;},empty(){this.value='';}});
    const frappe = {utils:{escape_html},ui:{form:{on:(name,obj)=>handlers[name]=obj},Dialog:class {
        constructor(opts){this.opts=opts;this.fields_dict={worksheet:{$wrapper:wrap()}};dialogs.push(this);}
        show(){this.shown=true;}
    }}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frappe_hr_pph21/public/js/salary_slip.js'),'utf8'),{frappe,__:x=>x});
    return {ui:frappe.hr_pph21_worksheet,refresh:handlers['Salary Slip'].refresh,dialogs,wrap};
}
test('monthly worksheet uses saved values and Indonesian money/rate formatting',()=>{
    const {ui}=harness(), data=fixture('monthly'), before=JSON.stringify(data);
    const html=ui.render(data);
    assert.match(html,/September 2026/);assert.match(html,/Rp 10\.666\.666/);
    assert.match(html,/2,5%/);assert.match(html,/26 Agustus 2026 – 25 September 2026/);
    assert.match(html,/Objek pajak · noncash/);assert.match(html,/Pengurang tahunan/);
    assert.doesNotMatch(html,/PPh21 setahun|<pre|annual_tax/);
    assert.equal(JSON.stringify(data),before);
});
test('final refund shows annual reconciliation instead of misleading zero TER',()=>{
    const {ui}=harness(), html=ui.render(fixture('final'));
    assert.match(html,/Rekonsiliasi pajak tahunan/);assert.match(html,/PPh21 setahun/);
    assert.match(html,/Rp 230\.179/);assert.match(html,/Rp 54\.000\.000/);
    assert.doesNotMatch(html,/Tarif efektif rata-rata|TER bulanan/);
});
test('untrusted snapshot text is escaped in all displayed sections',()=>{
    const {ui}=harness(), data=fixture('monthly'), payload='<img src=x onerror=alert(1)>';
    data.company=data.settings_name=data.employee=payload;data.prior_slips=[payload];
    data.components[0].component=data.components[0].additional_salary=payload;
    data.accounts.tax=data.opening.opening_reference=payload;
    const html=ui.render(data);
    assert.doesNotMatch(html,/<img|<script/);assert.match(html,/&lt;img/);
});
test('legacy snapshot dates stay unavailable and do not come from current slip',()=>{
    const {ui}=harness(), data=fixture('monthly');
    for(const key of ['payment_date','payroll_start_date','payroll_end_date','tax_period_basis']) delete data[key];
    const html=ui.render(data);
    assert.match(html,/Kertas kerja versi lama/);assert.match(html,/<dd>— – —<\/dd>/);
    assert.match(html,/Rp 10\.666\.666/);
});
test('malformed or absent snapshots give a helpful message without exposing JSON',()=>{
    const {ui}=harness();
    for(const raw of ['{broken','null','[]','{}','{"result":[]}','{"result":{}}']) {
        assert.equal(ui.read(raw),null);assert.match(ui.render(ui.read(raw)),/tidak dapat dibaca/);
    }
});
test('missing numeric values do not appear as zero, but saved zero does',()=>{
    const {ui}=harness(), data=fixture('monthly');
    delete data.result.allowance;data.result.withholding='NaN';data.result.refund='0';
    const html=ui.render(data,{compact:true});
    assert.match(html,/Tunjangan PPh21<\/span><strong>—/);
    assert.match(html,/PPh21 dipotong<\/span><strong>—/);
    assert.match(html,/PPh21 dikembalikan<\/span><strong>Rp 0/);
});
test('Salary Slip shows inline summary and opens detailed dialog with latest snapshot',()=>{
    const h=harness(), wrapper=h.wrap(), props=[], buttons={};
    const frm={doc:{pph21_tax_snapshot:JSON.stringify(fixture('monthly'))},fields_dict:{pph21_tax_worksheet:{$wrapper:wrapper}},is_dirty:()=>true,
        set_df_property:(...p)=>props.push(p),add_custom_button:(label,fn)=>buttons[label]=fn};
    h.refresh(frm);
    assert.ok(props.some(p=>p[0]==='pph21_tax_snapshot' && p[2]===1));
    assert.match(wrapper.value,/belum disimpan/);assert.doesNotMatch(wrapper.value,/Komponen penghasilan dan potongan/);
    frm.doc.pph21_tax_snapshot=JSON.stringify(fixture('final'));
    buttons['Kertas Kerja PPh 21']();
    assert.equal(h.dialogs[0].shown,true);assert.match(h.dialogs[0].fields_dict.worksheet.$wrapper.value,/Rekonsiliasi pajak tahunan/);
    frm.doc.pph21_tax_snapshot='';h.refresh(frm);assert.equal(wrapper.value,'');
});
test('dialog still works if HTML custom field is unavailable before migration',()=>{
    const h=harness();let click;
    h.refresh({doc:{pph21_tax_snapshot:JSON.stringify(fixture('monthly'))},fields_dict:{},set_df_property(){},add_custom_button:(label,fn)=>click=fn});
    click();assert.equal(h.dialogs[0].shown,true);
});
