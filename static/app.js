const $ = id => document.getElementById(id);
let register = false, dataset = null, result = null, mode = 'one';
const number = n => n == null ? 'Not defined' : new Intl.NumberFormat('en-KE', {maximumFractionDigits:2, minimumFractionDigits:2}).format(n);
const money = n => `${$('currency').value} ${number(n)}`;
const month = d => new Date(d+'-01T12:00:00').toLocaleDateString('en-GB',{month:'short',year:'numeric'});
async function api(path, body = {}, file = null) {
  const response = await fetch(path, {method:'POST',headers:{'X-Cashflow-Request':'1',...(file ? {'X-Filename':encodeURIComponent(file.name)} : {'Content-Type':'application/json'})},body:file || JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || 'Request failed. Please try again.');
  return data;
}
function setDataset(data) {
  dataset = data;
  $('run').disabled = !data;
  $('dataset-status').hidden = !data;
  if (!data) return;
  $('dataset-status').textContent = `✓ ${data.filename} · ${data.rows.toLocaleString()} transactions · ${data.months} months (${month(data.first)} – ${month(data.last)})${data.duplicates ? ` · ${data.duplicates} duplicate rows retained; review your source.` : ''}`;
  const date = new Date(data.last+'-01T12:00:00');
  const format = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
  date.setMonth(date.getMonth()+1); $('end-month').min = format(date);
  date.setMonth(date.getMonth()+59); $('end-month').max = format(date);
  date.setMonth(date.getMonth()-54); $('end-month').value = format(date);
  $('horizon-note').textContent = `History ends ${month(data.last)}. Forecast up to 60 months ahead.`;
  result = null;
  $('results').hidden = true; $('empty-state').hidden = false;
}
async function restore() {
  const response = await fetch('/api/me');
  const state = await response.json();
  $('auth').hidden = !!state.user; $('workspace').hidden = !state.user;
  if (state.user) {
    $('shop-name').textContent = state.user.name;
    $('avatar').textContent = state.user.name[0].toUpperCase();
    setDataset(state.dataset);
  }
}
$('auth-switch').onclick = () => {
  register = !register;
  $('name-field').hidden = !register; $('name').required = register;
  $('auth-title').textContent = register ? 'Your next chapter.' : 'Welcome back.';
  $('auth-subtitle').textContent = register ? 'Create an account to start planning for your shop.' : 'Sign in to your shop’s forecasting workspace.';
  $('auth-submit').textContent = register ? 'Create account →' : 'Sign in →';
  $('switch-copy').textContent = register ? 'Already have an account?' : 'New to ShopFlow?';
  $('auth-switch').textContent = register ? 'Sign in' : 'Create an account';
  $('password').autocomplete = register ? 'new-password' : 'current-password';
  $('auth-error').textContent = '';
};
$('auth-form').onsubmit = async e => {
  e.preventDefault(); $('auth-error').textContent = ''; $('auth-submit').disabled = true;
  try { await api(register ? '/api/register' : '/api/login', {name:$('name').value,email:$('email').value,password:$('password').value}); $('password').value = ''; await restore(); }
  catch (e) { $('auth-error').textContent = e.message; }
  finally { $('auth-submit').disabled = false; }
};
$('logout').onclick = async () => {
  try { await api('/api/logout'); result = null; dataset = null; $('results').hidden=true; $('empty-state').hidden=false; await restore(); }
  catch(e) { $('workspace-error').textContent=e.message; }
};
async function upload(file) {
  if (!file) return;
  if (file.size > 30*1024*1024) { $('workspace-error').textContent='Please choose a file under 30 MB.'; return; }
  $('workspace-error').textContent=''; $('activity').textContent='Reading and validating your transactions…';
  $('run').disabled=true; $('demo').disabled=true; $('upload').disabled=true;
  try { setDataset(await api('/api/upload', {}, file)); $('activity').textContent='Your data is ready. Choose your horizon and generate a forecast.'; }
  catch(e) { $('workspace-error').textContent=e.message; $('activity').textContent=''; }
  finally { $('run').disabled=!dataset; $('demo').disabled=false; $('upload').disabled=false; $('upload').value=''; }
}
$('upload').onchange = e => upload(e.target.files[0]);
const drop = $('drop-zone');
drop.ondragover = e => {e.preventDefault();drop.classList.add('drag');};
drop.ondragleave = () => drop.classList.remove('drag');
drop.ondrop = e => {e.preventDefault();drop.classList.remove('drag');if (!$('upload').disabled) upload(e.dataTransfer.files[0]);};
$('demo').onclick = async () => {
  $('workspace-error').textContent=''; $('demo').disabled=true; $('run').disabled=true;
  try { setDataset(await api('/api/demo')); $('activity').textContent='Sample data loaded. Generate a forecast to explore the model.'; }
  catch(e) { $('workspace-error').textContent=e.message; }
  finally { $('demo').disabled=false; $('run').disabled=!dataset; }
};
$('run').onclick = async () => {
  $('workspace-error').textContent='';
  if (!$('end-month').reportValidity()) return;
  $('run').disabled=true; $('activity').textContent='Training the model, checking holdout scores, and forecasting…';
  try { result = await api('/api/forecast',{end:$('end-month').value}); render(); $('activity').textContent='Forecast ready. Explore the outlook below.'; $('results').scrollIntoView({behavior:'smooth',block:'start'}); }
  catch(e) { $('workspace-error').textContent=e.message; $('activity').textContent=''; }
  finally { $('run').disabled=false; }
};
function renderMetrics() {
  const m = mode === 'one' ? result.metrics : result.recursive_metrics;
  const entries = [['MAE',money(m.mae)],['RMSE',money(m.rmse)],['R²',m.r2 == null ? 'Not defined' : m.r2.toFixed(3)],['WAPE',m.wape == null ? 'Not defined' : number(m.wape)+'%']];
  $('metric-grid').replaceChildren(...entries.map(([label,value]) => {const d=document.createElement('div');const s=document.createElement('span');s.textContent=label;const b=document.createElement('strong');b.textContent=value;d.append(s,b);return d;}));
  $('evaluation-description').textContent = `Trained on ${result.training_months} eligible months; evaluated on the last ${result.test_months} months (${month(result.evaluation[0].date)} – ${month(result.evaluation.at(-1).date)}).`;
  $('baseline').textContent = `Same-month-last-year baseline MAE: ${money(result.baseline_metrics.mae)}. Model bias: ${money(m.bias)}. ${m.mae < result.baseline_metrics.mae ? 'The model has lower absolute error than this baseline.' : 'The seasonal baseline has equal or lower absolute error than the model.'}`;
  document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('selected', b.dataset.mode===mode));
}
document.querySelectorAll('[data-mode]').forEach(b => b.onclick = () => {mode=b.dataset.mode;renderMetrics();});
function render() {
  if (!result) return;
  $('empty-state').hidden=true; $('results').hidden=false;
  const f = result.forecast, lowest=f.reduce((a,b)=>a.cashflow<b.cashflow?a:b);
  $('forecast-period').textContent=`${month(f[0].date)} – ${month(f.at(-1).date)} · ${f.length} ${f.length===1?'month':'months'} ahead`;
  $('total').textContent=money(result.total); $('average').textContent=money(result.total/f.length); $('lowest').textContent=money(lowest.cashflow); $('lowest-caption').textContent=month(lowest.date); $('total-caption').textContent=`Sum of ${f.length} monthly predictions`;
  $('forecast-rows').replaceChildren(...f.map(r=>{const tr=document.createElement('tr');const td=document.createElement('td');td.textContent=month(r.date);const amount=document.createElement('td');amount.textContent=money(r.cashflow);amount.classList.toggle('negative',r.cashflow<0);tr.append(td,amount);return tr;}));
  $('coefficients').textContent='Final model coefficients\n'+Object.entries(result.coefficients).map(([k,v])=>`${k}: ${number(v)}`).join('\n')+`\nintercept: ${number(result.intercept)}`;
  renderMetrics(); drawChart();
}
function drawChart() {
  const h=result.history, f=result.forecast, all=[...h,...f];
  const width=960,height=285,left=83,right=25,top=20,bottom=42;
  let min=Math.min(0,...all.map(d=>d.cashflow)),max=Math.max(...all.map(d=>d.cashflow));
  const pad=(max-min || 1)*.1; min-=pad;max+=pad;
  const x=i=>left+i*(width-left-right)/(all.length-1),y=v=>top+(max-v)*(height-top-bottom)/(max-min);
  const path=(data,start)=>data.map((d,i)=>`${i?'L':'M'}${x(start+i).toFixed(2)},${y(d.cashflow).toFixed(2)}`).join(' ');
  let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Historical cashflow and future forecast line chart"><title>Monthly cashflow in ${$('currency').value}</title>`;
  for(let i=0;i<=4;i++){const v=min+(max-min)*i/4, yy=y(v);svg+=`<line x1="${left}" y1="${yy}" x2="${width-right}" y2="${yy}" stroke="#e9eee2"/><text x="${left-12}" y="${yy+4}" text-anchor="end">${new Intl.NumberFormat('en',{notation:'compact',maximumFractionDigits:1}).format(v)}</text>`;}
  const split=x(h.length-1);
  svg+=`<rect x="${split}" y="${top}" width="${width-right-split}" height="${height-top-bottom}" fill="#b5d394" opacity=".09"/><line x1="${split}" y1="${top}" x2="${split}" y2="${height-bottom}" stroke="#cbd9bd" stroke-dasharray="4 4"/><path d="${path(h,0)}" fill="none" stroke="#315e4a" stroke-width="2.5"/><path d="${path([h.at(-1),...f],h.length-1)}" fill="none" stroke="#92b568" stroke-width="2.5" stroke-dasharray="6 5"/>`;
  all.forEach((d,i)=>{svg+=`<circle cx="${x(i)}" cy="${y(d.cashflow)}" r="3" fill="${i<h.length?'#315e4a':'#92b568'}"><title>${month(d.date)}: ${money(d.cashflow)}</title></circle>`;});
  const indexes=[...new Set([0,Math.floor(all.length*.25),Math.floor(all.length*.5),Math.floor(all.length*.75),all.length-1])];
  indexes.forEach(i=>svg+=`<text x="${x(i)}" y="${height-14}" text-anchor="${i===0?'start':i===all.length-1?'end':'middle'}">${month(all[i].date)}</text>`);
  $('forecast-chart').innerHTML=svg+'</svg>';
}
$('currency').onchange=render;
$('download').onclick=()=>{if(!result)return;const csv='Month,Predicted Cashflow\r\n'+result.forecast.map(r=>`${r.date},${r.cashflow.toFixed(2)}`).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='shopflow-forecast.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
restore().catch(()=>{$('auth-error').textContent='Cannot reach the server. Start server.py and reload this page.';});
