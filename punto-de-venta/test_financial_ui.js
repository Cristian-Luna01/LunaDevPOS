"use strict";
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/static/app.js','utf8');
const cents=source.slice(source.indexOf('const cents ='),source.indexOf('let me,'));
const formulas=source.slice(source.indexOf('function promotionTotal('),source.indexOf('function renderCart('));
const preview=source.slice(source.indexOf('function updatePaymentPreview('),source.indexOf('function renderReceipt('));
const nodes={dialogForm:{elements:{method:{value:'cash'},received:{value:'0'},credit_customer:{value:'1'}}},changeAmount:{},dialogError:{}};
const ctx={window:{},cart:[],customer:()=>({discount_bps:ctx.rate}),rate:0,$:id=>nodes[id],money:c=>String(c)};vm.createContext(ctx);
vm.runInContext([cents,formulas,preview].join(String.fromCharCode(10)),ctx);
const parse=vm.runInContext('cents',ctx);
for(const [value,expected] of [['',0],['20',2000],['20.5',2050],['0.01',1],[' 30 ',3000]])assert.equal(parse(value),expected);
for(const value of ['-1','1.001','abc','Infinity','1e2','0,50'])assert.throws(()=>parse(value));
for(let i=0;i<3000;i++){
 const price=1+(i*7919)%999999,qty=1+i%19,rate=(i*137)%10001,bundle=1+i%5,promo=1+(i*31)%(price*bundle);
 ctx.rate=rate;ctx.cart=[{quantity:qty,product:{price_cents:price,promotion:{bundle_quantity:bundle,price_cents:promo}}}];
 const gross=BigInt(price)*BigInt(qty),discount=(gross*BigInt(rate)+5000n)/10000n;
 const offer=BigInt(Math.floor(qty/bundle)*promo+(qty%bundle)*price);
 const expected=gross-discount<offer?gross-discount:offer;
 const result=ctx.totals();assert.equal(BigInt(result.total),expected);assert.equal(BigInt(result.discount),gross-expected);
}
nodes.dialogForm.elements.received.value='350';assert.equal(ctx.updatePaymentPreview(31500),true);assert.equal(nodes.changeAmount.textContent,'3500');
nodes.dialogForm.elements.received.value='0';assert.equal(ctx.updatePaymentPreview(0),true);
nodes.dialogForm.elements.received.value='10';assert.equal(ctx.updatePaymentPreview(0),false);
nodes.dialogForm.elements.method.value='on_account';assert.equal(ctx.updatePaymentPreview(0),false);
console.log('OK: 3000 combinaciones de descuento/promoción, importes, cambio y total cero');
