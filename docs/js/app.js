/* FX Atlas — interface. Ce fichier n'invente aucun chiffre : tout vient de data/*.json,
   écrits chaque jour par le robot. Une valeur absente s'affiche « n/d ». */
(() => {
'use strict';

const METRICS = [
  {key:'policy',     label:'Taux directeur', short:'Taux dir.', unit:'%',  scale:'seq', desc:'Taux directeur nominal fixé par la banque centrale.'},
  {key:'real',       label:'Taux réel',      short:'Taux réel', unit:'%',  scale:'div', desc:'Taux directeur moins inflation sur un an (ex post).'},
  {key:'cpi',        label:'Inflation',      short:'Inflation', unit:'%',  scale:'seq', desc:'Inflation sur un an (indice des prix à la consommation).'},
  {key:'gap',        label:'Inflation gap',  short:'Infl. gap', unit:'pt', scale:'div', desc:'Inflation moins cible de la banque centrale.'},
  {key:'policy_12m', label:'Variation du taux sur 12 mois', short:'Δ taux 12 m', unit:'pt', scale:'div', desc:'Taux directeur actuel moins taux d’il y a un an : montre le sens du cycle.'},
  {key:'carry_usd',  label:'Écart de taux vs États-Unis', short:'Écart vs US', unit:'pt', scale:'div', desc:'Taux directeur moins taux de la Fed : idée du portage (carry) face au dollar.'},
  {key:'y10',        label:'Taux à 10 ans',  short:'10 ans',    unit:'%',  scale:'seq', desc:'Rendement de l’emprunt d’État à 10 ans (moyenne mensuelle).'},
  {key:'fx_ytd',     label:'Devise vs USD depuis le 1er janvier', short:'Devise vs USD (YTD)', unit:'%', scale:'div', desc:'Variation de la devise face au dollar depuis le dernier fixing de l’an dernier. Positif = la devise s’est appréciée.'},
];
const M = Object.fromEntries(METRICS.map(m => [m.key, m]));
const SEQ = ['#1d2a6b','#43308f','#7d2f91','#b83b7f','#e45d5d','#f58c3f','#fbc04f','#fde98a'];
const DIV = ['#1f5fa8','#3f86c4','#8cb9dd','#dcd8cf','#f2a585','#d9604c','#ad1f2c'];
const COL_NODATA = '#3a4252', COL_OUT = '#18202e';
const MONTHS = ['janv.','févr.','mars','avr.','mai','juin','juil.','août','sept.','oct.','nov.','déc.'];
const STATUS = {ancien:'ancienne valeur', pas_a_jour:'pas à jour', a_verifier:'à vérifier', nd:'n/d'};

const S = {atlas:null, hist:null, fx:null, log:null, metric:'policy', sel:null, a3:{}, globe:null, chart:null, flat:false, hover:null};
const $ = (s, r=document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// ---------- formats ----------
function fmtNum(v, d=2){ return v==null||isNaN(v) ? 'n/d' : v.toLocaleString('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d}); }
function fmtVal(v, unit, signed=false, d=2){
  if (v==null||isNaN(v)) return 'n/d';
  const s = (signed && v>0 ? '+' : '') + fmtNum(v,d);
  return unit==='pt' ? s+' pt' : s+' %';
}
function fmtMetric(key, v){ const m=M[key]; return fmtVal(v==null?v:Math.round(v*100)/100, m.unit, m.scale==='div'); }
function fmtDate(s){
  if (!s) return 'n/d';
  const p = s.split('-');
  if (p.length===2) return MONTHS[+p[1]-1]+' '+p[0];
  return (+p[2])+' '+MONTHS[+p[1]-1]+' '+p[0];
}
function fmtDateTime(iso){
  try { return new Date(iso).toLocaleString('fr-FR',{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Paris'})+' (Paris)'; }
  catch(e){ return iso; }
}
function todayISO(){ const d=new Date(); return new Date(d.getTime()-d.getTimezoneOffset()*6e4).toISOString().slice(0,10); }
function daysTo(s){ const a=new Date(todayISO()+'T00:00:00'), b=new Date(s+'T00:00:00'); return Math.round((b-a)/864e5); }
function countdown(s){
  if (!s) return '';
  const n = daysTo(s);
  if (n===0) return 'aujourd’hui'; if (n===1) return 'demain'; if (n<0) return `il y a ${-n} j`;
  return `dans ${n} j`;
}
function badge(st){ return STATUS[st] && st!=='nd' ? `<span class="badge ${st}">${STATUS[st]}</span>` : ''; }
function signCls(v){ return v==null ? '' : v>0 ? 'pos' : v<0 ? 'neg' : ''; }

// ---------- couleurs ----------
function lerpHex(a,b,t){ const pa=parseInt(a.slice(1),16), pb=parseInt(b.slice(1),16);
  const r=(pa>>16)+(((pb>>16)-(pa>>16))*t), g=((pa>>8)&255)+((((pb>>8)&255)-((pa>>8)&255))*t), bl=(pa&255)+(((pb&255)-(pa&255))*t);
  return '#'+((1<<24)+(Math.round(r)<<16)+(Math.round(g)<<8)+Math.round(bl)).toString(16).slice(1); }
function ramp(stops, t){ t=Math.max(0,Math.min(1,t)); const x=t*(stops.length-1), i=Math.min(stops.length-2,Math.floor(x)); return lerpHex(stops[i],stops[i+1],x-i); }
function domain(key){
  const m = M[key];
  const vals = Object.values(S.atlas.countries).map(c => c.metrics?.[key]?.value).filter(v => v!=null && !isNaN(v));
  if (!vals.length) return null;
  if (m.scale==='div'){
    const ab = vals.map(Math.abs).sort((a,b)=>a-b);
    let hi = ab[ab.length-1], over=false;
    if (ab.length>3 && hi > 2.2*ab[ab.length-2]) { hi = ab[ab.length-2]*1.1; over=true; }
    hi = hi || 1;
    return {lo:-hi, hi, over, div:true};
  }
  const s = [...vals].sort((a,b)=>a-b);
  let lo = Math.min(0, s[0]), hi = s[s.length-1], over=false;
  if (s.length>3 && hi > 2.2*s[s.length-2]) { hi = s[s.length-2]*1.1; over=true; }
  if (hi===lo) hi = lo+1;
  return {lo, hi, over, div:false};
}
function colorFor(key, v, dom){
  if (v==null || !dom) return COL_NODATA;
  const t = (v-dom.lo)/(dom.hi-dom.lo);
  return ramp(dom.div?DIV:SEQ, t);
}

// ---------- données ----------
async function getJSON(u){ const r = await fetch(u+'?v='+Date.now()); if(!r.ok) throw new Error(u+' '+r.status); return r.json(); }

async function init(){
  try {
    [S.atlas, S.hist, S.fx, S.log, S.geo] = await Promise.all([
      getJSON('data/atlas.json'), getJSON('data/history.json'), getJSON('data/fx.json'),
      getJSON('data/log.json').catch(()=>null), getJSON('vendor/countries.geojson')]);
  } catch(e){
    $('#panel').innerHTML = `<div class="empty"><h2>Données indisponibles</h2><p>Les fichiers de données n’ont pas pu être chargés (${esc(e.message)}).</p></div>`;
    return;
  }
  for (const c of Object.values(S.atlas.countries)) for (const a3 of c.geo) S.a3[a3] = c.code;
  const h = location.hash.slice(1).split('/');
  if (M[h[1]]) S.metric = h[1];
  renderFresh(); renderMetricBar(); initGlobe(); renderLegend(); renderPanel();
  renderCalendar(); renderFX(); renderRank(); renderMethod();
  setupTabs(h[0]);
  if (h[2] && S.atlas.countries[h[2]]) select(h[2]);
}

function renderFresh(){
  const q = S.atlas.quality || {}, n = (q.missing||[]).length;
  const cls = n===0 ? '' : (q.missing_share>0.2 ? 'bad' : 'warn');
  const txt = n===0 ? 'Toutes les données essentielles à jour' : `${n} donnée${n>1?'s':''} pas à jour`;
  $('#fresh').innerHTML = `<span class="long">Robot : ${esc(fmtDateTime(S.atlas.generated_at))}</span>
    <span class="pill ${cls}" title="Détail dans l’onglet Sources & qualité" style="cursor:pointer" id="qpill"><i></i>${txt}</span>`;
  $('#qpill').onclick = () => showView('method');
}

// ---------- onglets ----------
function setupTabs(initial){
  document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => showView(b.dataset.view));
  if (initial && $('#view-'+initial)) showView(initial, true);
}
function showView(v, quiet){
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('on', b.dataset.view===v));
  document.querySelectorAll('section.view').forEach(s => s.classList.toggle('on', s.id==='view-'+v));
  if (v==='globe') resizeGlobe();
  if (!quiet) updateHash(v);
}
function currentView(){ return document.querySelector('#tabs button.on')?.dataset.view || 'globe'; }
function updateHash(v){ history.replaceState(null,'','#'+[v||currentView(), S.metric, S.sel||''].join('/').replace(/\/$/,'')); }

// ---------- barre des métriques & légende ----------
function renderMetricBar(){
  $('#metricBar').innerHTML = METRICS.map(m => `<button data-k="${m.key}" class="${m.key===S.metric?'on':''}" title="${esc(m.desc)}">${esc(m.short)}</button>`).join('');
  $('#metricBar').querySelectorAll('button').forEach(b => b.onclick = () => setMetric(b.dataset.k));
}
function setMetric(k){
  S.metric = k;
  $('#metricBar').querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.k===k));
  refreshColors(); renderLegend(); if (!S.sel) renderPanel(); updateHash();
}
function renderLegend(){
  const m = M[S.metric], dom = domain(S.metric);
  if (!dom){ $('#legend').innerHTML = `<div class="t">${esc(m.label)} : aucune donnée</div>`; return; }
  const stops = (dom.div?DIV:SEQ).map((c,i,a)=>`${c} ${Math.round(i/(a.length-1)*100)}%`).join(',');
  const mid = (dom.lo+dom.hi)/2;
  $('#legend').innerHTML = `<div class="t"><span>${esc(m.label)}</span><span class="faint">${m.scale==='div'?'froid = négatif · chaud = positif':'plus chaud = plus élevé'}</span></div>
    <div class="bar" style="background:linear-gradient(90deg,${stops})"></div>
    <div class="ticks"><span>${dom.over&&dom.div?'≤ ':''}${fmtVal(dom.lo,m.unit,dom.div,1)}</span><span>${fmtVal(mid,m.unit,dom.div,1)}</span><span>${dom.over?'≥ ':''}${fmtVal(dom.hi,m.unit,dom.div,1)}</span></div>
    <div class="nd"><span><b style="background:${COL_NODATA}"></b>suivi, valeur n/d</span><span><b style="background:${COL_OUT};border:1px solid #2c3d5c"></b>non suivi</span></div>`;
}

// ---------- globe ----------
function featColor(f){
  const code = S.a3[f.properties.a3];
  if (!code) return COL_OUT;
  const v = S.atlas.countries[code].metrics?.[S.metric]?.value;
  return colorFor(S.metric, v, S._dom);
}
function tipHTML(f){
  const code = S.a3[f.properties.a3];
  if (!code) return `<div class="tip"><b>${esc(f.properties.name_fr)}</b><span class="faint">Non suivi</span></div>`;
  const c = S.atlas.countries[code], mm = c.metrics?.[S.metric] || {};
  const sub = c.geo.length>1 ? `<span class="faint">${esc(f.properties.name_fr)} · ${esc(c.name)}</span><br>` : '';
  return `<div class="tip"><b>${esc(c.geo.length>1?c.name:c.name)}</b>${sub}<span class="faint">${esc(M[S.metric].label)}</span><br><span class="v">${fmtMetric(S.metric, mm.value)}</span> ${badge(mm.status)}${mm.date?`<br><span class="faint">valeur du ${fmtDate(mm.date)}</span>`:''}</div>`;
}
function initGlobe(){
  S._dom = domain(S.metric);
  const feats = S.geo.features.filter(f => f.properties.a3 !== 'ATA');
  const el = $('#globe');
  let g;
  try {
    g = Globe({animateIn:true})(el)
      .backgroundColor('rgba(0,0,0,0)')
      .showAtmosphere(true).atmosphereColor('#4a7bd6').atmosphereAltitude(0.16)
      .polygonsData(feats)
      .polygonCapColor(featColor)
      .polygonSideColor(() => 'rgba(5,10,20,0.55)')
      .polygonStrokeColor(() => 'rgba(11,18,32,0.9)')
      .polygonAltitude(f => f===S.hover ? 0.035 : (S.a3[f.properties.a3] && S.a3[f.properties.a3]===S.sel ? 0.03 : (S.a3[f.properties.a3] ? 0.012 : 0.004)))
      .polygonLabel(tipHTML)
      .polygonsTransitionDuration(250)
      .onPolygonHover(f => { S.hover = f; el.style.cursor = f && S.a3[f.properties.a3] ? 'pointer' : 'grab'; g.polygonAltitude(g.polygonAltitude()); })
      .onPolygonClick(f => { const c = S.a3[f.properties.a3]; if (c) select(c, true); });
    const mat = g.globeMaterial(); mat.color.set('#0f1c33'); mat.emissive && mat.emissive.set('#0a1424'); mat.shininess = 6;
    g.pointOfView({lat:28, lng:10, altitude:2.3});
    const ctl = g.controls(); ctl.autoRotate = true; ctl.autoRotateSpeed = 0.35; ctl.minDistance = 140; ctl.maxDistance = 650;
    el.addEventListener('pointerdown', () => { ctl.autoRotate = false; $('#btnSpin').classList.remove('on'); });
    S.globe = g;
  } catch(e){
    console.warn('Globe 3D indisponible, carte plate utilisée', e);
    S.flat = true; $('#stage').classList.add('flat'); $('#btnFlat').textContent = 'Globe 3D';
  }
  new ResizeObserver(resizeGlobe).observe($('#stage'));
  resizeGlobe();
  drawFlat(feats);
  $('#btnSpin').onclick = () => { if(!S.globe) return; const c=S.globe.controls(); c.autoRotate=!c.autoRotate; $('#btnSpin').classList.toggle('on', c.autoRotate); };
  $('#btnFlat').onclick = () => { if(!S.globe) return; S.flat = !S.flat; $('#stage').classList.toggle('flat', S.flat); $('#btnFlat').textContent = S.flat ? 'Globe 3D' : 'Carte plate'; $('#btnFlat').classList.toggle('on', S.flat); };
}
function resizeGlobe(){ if (!S.globe) return; const r = $('#stage').getBoundingClientRect(); if (r.width) S.globe.width(r.width).height(r.height); }
function refreshColors(){
  S._dom = domain(S.metric);
  if (S.globe) S.globe.polygonCapColor(featColor);
  document.querySelectorAll('#flat path').forEach(p => { p.setAttribute('fill', featColor(p.__f)); });
}
function centroid(code){
  const c = S.atlas.countries[code]; let best=null, area=0;
  for (const f of S.geo.features) if (c.geo.includes(f.properties.a3)) {
    const polys = f.geometry.type==='Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const p of polys){ const ring=p[0]; let xs=ring.map(q=>q[0]), ys=ring.map(q=>q[1]);
      const a=(Math.max(...xs)-Math.min(...xs))*(Math.max(...ys)-Math.min(...ys));
      if (a>area){ area=a; best={lng:(Math.max(...xs)+Math.min(...xs))/2, lat:(Math.max(...ys)+Math.min(...ys))/2}; } }
  }
  if (code==='XM') best = {lat:48, lng:9};
  return best;
}

// ---------- carte plate ----------
function drawFlat(feats){
  const W=1000, LAT0=84, LAT1=-58, H=W*(LAT0-LAT1)/360;
  const px = ([lon,lat]) => `${((lon+180)/360*W).toFixed(1)},${((LAT0-lat)/(LAT0-LAT1)*H).toFixed(1)}`;
  const ns='http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns,'svg'); svg.setAttribute('viewBox',`0 0 ${W} ${H.toFixed(0)}`); svg.setAttribute('preserveAspectRatio','xMidYMid meet');
  const tip = $('#flatTip');
  for (const f of feats){
    const polys = f.geometry.type==='Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    let d=''; for (const p of polys) for (const ring of p) d += 'M'+ring.map(px).join('L')+'Z';
    const path = document.createElementNS(ns,'path'); path.setAttribute('d', d); path.__f = f;
    path.setAttribute('fill', featColor(f)); path.setAttribute('stroke','#0b1220'); path.setAttribute('stroke-width','0.5');
    const code = S.a3[f.properties.a3];
    if (code){ path.style.cursor='pointer'; path.onclick = () => select(code, true); }
    path.onmousemove = e => { const r=$('#stage').getBoundingClientRect(); tip.innerHTML = tipHTML(f).replace(/^<div class="tip">|<\/div>$/g,''); tip.style.display='block'; tip.style.left=(e.clientX-r.left+14)+'px'; tip.style.top=(e.clientY-r.top+14)+'px'; path.setAttribute('stroke','#e6ebf3'); };
    path.onmouseleave = () => { tip.style.display='none'; path.setAttribute('stroke','#0b1220'); };
    svg.appendChild(path);
  }
  $('#flat').appendChild(svg);
}

// ---------- sélection & fiche pays ----------
function select(code, fly){
  S.sel = code;
  if (S.globe){
    S.globe.polygonAltitude(S.globe.polygonAltitude());
    if (fly){ const c = centroid(code); if (c){ S.globe.controls().autoRotate=false; $('#btnSpin').classList.remove('on'); S.globe.pointOfView({...c, altitude:1.7}, 900); } }
  }
  if (currentView()!=='globe') showView('globe');
  renderPanel(); updateHash();
  if (window.innerWidth<=980) $('#panel').scrollIntoView({behavior:'smooth', block:'start'});
}

function kpi(label, rec, key, opts={}){
  const m = M[key]; const v = rec?.value;
  const val = key ? fmtMetric(key, v) : (v==null?'n/d':fmtVal(v,'%'));
  const cls = m && m.scale==='div' ? signCls(v) : '';
  const derivedB = rec?.source==='Calcul FX Atlas' ? '<span class="badge calc">calcul</span>' : '';
  const date = rec?.date ? `valeur du ${fmtDate(rec.date)}` : '';
  const title = [rec?.source, rec?.series, rec?.note].filter(Boolean).join(' — ');
  return `<div class="kpi ${opts.big?'big':''}" title="${esc(title)}"><div class="l">${esc(label)} ${derivedB}${badge(rec?.status)}</div>
    <div class="v ${cls}">${val}</div><div class="d">${esc(opts.sub || date)}</div></div>`;
}

function renderPanel(){
  const P = $('#panel');
  if (!S.sel){ P.innerHTML = overviewHTML(); bindOverview(); return; }
  const c = S.atlas.countries[S.sel], m = c.metrics, t = c.target || {}, g = c.governor || {}, mt = c.meetings || {};
  const pol = m.policy || {};
  const range = pol.range ? `fourchette ${fmtNum(pol.range[0])}–${fmtNum(pol.range[1])} %` : null;
  let meetHTML;
  const LC = mt.last_change;
  const lcHTML = LC ? `<div class="src" style="margin-top:6px">Dernier changement du taux : <b>${LC.bp>0?'+':''}${LC.bp} pb</b> → ${fmtNum(LC.new)} % (en vigueur le ${fmtDate(LC.date)}).</div>` : '';
  if (mt.status==='aucun') meetHTML = `<p class="muted" style="margin:0">${esc(mt.note||'Pas de calendrier publié.')}</p>${lcHTML}`;
  else {
    const L = mt.last, N = mt.next || {};
    const dec = L?.decision || {};
    const decTxt = !L ? 'non lue sur la page officielle' : dec.type==='hausse' ? `Hausse de ${dec.bp} pb` : dec.type==='baisse' ? `Baisse de ${Math.abs(dec.bp)} pb` : dec.type==='maintien' ? 'Maintien' : (dec.note ? 'Décision pas encore dans la série officielle' : 'Décision non déduite');
    meetHTML = `<div class="meet">
      <div class="kpi"><div class="l">Dernière réunion ${badge(mt.status==='pas_a_jour'?'pas_a_jour':null)}</div><div class="v">${L?fmtDate(L.date):'n/d'}</div>
        <div class="d"><span class="dec ${dec.type||''}">${esc(decTxt)}</span>${dec.new!=null?` → ${fmtNum(dec.new)} %`:''}</div></div>
      <div class="kpi"><div class="l">Prochaine réunion</div><div class="v">${N.date?fmtDate(N.date):'non publiée'}</div>
        <div class="d"><span class="count">${N.date?countdown(N.date):''}</span></div></div></div>
      ${lcHTML}
      ${mt.note?`<div class="src" style="margin-top:4px">${esc(mt.note)}</div>`:''}
      <div class="src" style="margin-top:6px">Calendrier : <a href="${esc(mt.source)}" target="_blank" rel="noopener">page officielle</a>${mt.checked?` · lu le ${fmtDate(mt.checked)}`:''}. Décision déduite de la série officielle du taux.</div>`;
  }
  const fxv = fxForCountry(c.currency);
  P.innerHTML = `<div class="panel-head">
      <h2>${esc(c.name)} <span class="ccy">${esc(c.currency)}</span></h2>
      <div class="cb">${esc(c.cb)}</div>
      <div class="gov" title="${esc(g.note||g.source||'')}">Dirigeant : ${g.name?`<a href="${esc(g.check_url||g.url)}" target="_blank" rel="noopener">${esc(g.name)}</a>`:'n/d <span class="faint">(nom non confirmé par une page officielle)</span>'}${g.since?` · depuis ${fmtDate(g.since)}`:''} ${badge(g.status)}</div>
    </div>
    <div class="panel-body">
      <div class="block"><h3>Taux &amp; inflation</h3><div class="kpis">
        ${kpi('Taux directeur', pol, 'policy', {sub: range ? range+' · '+(pol.date?'au '+fmtDate(pol.date):'') : null})}
        ${kpi('Taux réel', m.real, 'real')}
        ${kpi('Inflation (1 an)', m.cpi, 'cpi')}
        <div class="kpi" title="${esc([t.source,t.note].filter(Boolean).join(' — '))}"><div class="l">Cible d’inflation ${badge(t.status)}</div><div class="v" style="font-size:15px">${t.label?esc(t.label):'n/d'}</div><div class="d">${t.url?`<a href="${esc(t.url)}" target="_blank" rel="noopener">source officielle</a>`:esc(t.note||'')}</div></div>
        ${kpi('Inflation gap', m.gap, 'gap')}
        ${kpi('Δ taux sur 12 mois', m.policy_12m, 'policy_12m')}
        ${kpi('Écart vs taux US', m.carry_usd, 'carry_usd')}
        ${kpi('Taux à 10 ans', m.y10, 'y10')}
      </div>${pol.rate_note?`<div class="src" style="margin-top:6px">${esc(pol.rate_note)}</div>`:''}</div>
      <div class="block"><h3>Réunions</h3>${meetHTML}</div>
      <div class="block"><h3>Taux directeur et inflation sur 3 ans</h3><div class="chart-box"><canvas id="chart"></canvas></div></div>
      <div class="block"><h3>Devise : ${esc(c.currency)}</h3>${fxv}</div>
      <div class="block src"><h3>Sources</h3><ul>
        ${srcLine('Taux directeur', pol)}${srcLine('Inflation', m.cpi)}${srcLine('Taux 10 ans', m.y10)}
        <li>Dirigeant : ${g.source?esc(g.source):'n/d'}${g.checked?` (vérifié le ${fmtDate(g.checked)})`:''}</li>
        <li>Devise : ${esc(S.fx.source)}</li>
      </ul><button class="btn" id="backBtn" style="margin-top:8px">← Vue d’ensemble</button></div>
    </div>`;
  $('#backBtn').onclick = () => { S.sel=null; if (S.globe) S.globe.polygonAltitude(S.globe.polygonAltitude()); renderPanel(); updateHash(); };
  drawChart(c);
}
function srcLine(label, r){
  if (!r || r.value==null && !r.source) return `<li>${label} : n/d</li>`;
  return `<li>${label} : ${r.url?`<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.source)}</a>`:esc(r.source||'')} ${r.series?`<span class="faint">(${esc(r.series)})</span>`:''}${r.date?` — valeur du ${fmtDate(r.date)}`:''}</li>`;
}

function drawChart(c){
  if (S.chart){ S.chart.destroy(); S.chart=null; }
  const h = S.hist.countries[c.code] || {};
  const ts = s => new Date((s.length===7 ? s+'-15' : s)+'T00:00:00').getTime();
  const pol = (h.policy||[]).map(([d,v]) => ({x:ts(d), y:v}));
  if (pol.length){ const last = pol[pol.length-1]; const now = Date.now(); if (last.x < now) pol.push({x:now, y:last.y}); }
  const cpi = (h.cpi||[]).map(([d,v]) => ({x:ts(d), y:v}));
  const xmin = Date.now() - 3*365.25*864e5;
  const ds = [
    {label:'Taux directeur', data:pol, borderColor:'#f5a524', backgroundColor:'#f5a524', stepped:'before', borderWidth:2, pointRadius:0},
    {label:'Inflation (1 an)', data:cpi, borderColor:'#5aa9ff', backgroundColor:'#5aa9ff', borderWidth:2, pointRadius:0, tension:.2},
  ];
  if (c.target?.value!=null) ds.push({label:'Cible', data:[{x:xmin,y:c.target.value},{x:Date.now(),y:c.target.value}], borderColor:'#93a1b8', borderDash:[5,4], borderWidth:1, pointRadius:0});
  if (!pol.length && !cpi.length){ $('#chart').parentElement.innerHTML = '<p class="muted" style="padding:10px">Historique n/d</p>'; return; }
  S.chart = new Chart($('#chart'), {type:'line', data:{datasets:ds}, options:{
    responsive:true, maintainAspectRatio:false, animation:false, parsing:false,
    interaction:{mode:'nearest', axis:'x', intersect:false},
    scales:{
      x:{type:'linear', min:xmin, max:Date.now(), grid:{color:'#1c2840'}, ticks:{color:'#93a1b8', maxTicksLimit:6, callback:v=>{const d=new Date(v); return MONTHS[d.getMonth()]+' '+String(d.getFullYear()).slice(2);}}},
      y:{grid:{color:'#1c2840'}, ticks:{color:'#93a1b8', callback:v=>fmtNum(v,1)+' %'}}},
    plugins:{legend:{labels:{color:'#c9d2e0', boxWidth:12, font:{size:11}}},
      tooltip:{callbacks:{title:it=>{const d=new Date(it[0].parsed.x); return d.toLocaleDateString('fr-FR',{day:'numeric',month:'short',year:'numeric'});}, label:it=>`${it.dataset.label} : ${fmtNum(it.parsed.y)} %`}}}
  }});
}

// ---------- devises ----------
function fxRateAt(ccy, i){ if (ccy==='EUR') return 1; const a=S.fx.history.rates[ccy]; return a ? a[i] : null; }
function lastIdx(pred){ const d=S.fx.history.dates; for (let i=d.length-1;i>=0;i--) if (pred(i)) return i; return -1; }
function idxOnOrBefore(dateStr, ccys){ const d=S.fx.history.dates; for (let i=d.length-1;i>=0;i--) if (d[i]<=dateStr && ccys.every(c=>fxRateAt(c,i))) return i; return -1; }
function cross(x, base, i){ const rx=fxRateAt(x,i), rb=fxRateAt(base,i); return rx&&rb ? rb/rx : null; } // prix de 1 X en devise base
const WINDOWS = [['1J','1d'],['1S','7d'],['1M','1m'],['Depuis 1er janv.','ytd'],['1 an','1y']];
function refDate(nowStr, w){
  const d = new Date(nowStr+'T00:00:00');
  if (w==='1d') return null;
  if (w==='7d') d.setDate(d.getDate()-7);
  if (w==='1m') d.setMonth(d.getMonth()-1);
  if (w==='1y') d.setFullYear(d.getFullYear()-1);
  if (w==='ytd') return (d.getFullYear()-1)+'-12-31';
  return d.toISOString().slice(0,10);
}
function perf(x, base, w){
  if (x===base) return null;
  const i = lastIdx(i => fxRateAt(x,i) && fxRateAt(base,i)); if (i<0) return null;
  let j;
  if (w==='1d'){ j = i-1; while (j>=0 && !(fxRateAt(x,j)&&fxRateAt(base,j))) j--; }
  else j = idxOnOrBefore(refDate(S.fx.history.dates[i], w), [x,base]);
  if (j<0) return null;
  const a=cross(x,base,i), b=cross(x,base,j); return a&&b ? (a/b-1)*100 : null;
}
function fxForCountry(ccy){
  const i = lastIdx(k => fxRateAt('USD',k) && fxRateAt(ccy,k));
  if (i<0) return '<p class="muted">n/d</p>';
  const date = S.fx.history.dates[i];
  const base = ccy==='USD' ? 'EUR' : 'USD';
  const lines = [];
  if (ccy!=='EUR') lines.push(`1 EUR = <b class="num">${fmtNum(cross('EUR',ccy,i),4)}</b> ${ccy}`);
  if (ccy!=='USD') lines.push(`1 USD = <b class="num">${fmtNum(cross('USD',ccy,i),4)}</b> ${ccy}`);
  const cells = WINDOWS.map(([l,w]) => { const p = perf(ccy, base, w); return `<div class="kpi"><div class="l">${l}</div><div class="v ${signCls(p)}" style="font-size:14px">${p==null?'n/d':fmtVal(p,'%',true)}</div></div>`; }).join('');
  return `<div class="muted">${lines.join(' · ')}</div>
    <div class="src" style="margin:4px 0 8px">Taux de référence BCE du ${fmtDate(date)} (fixé vers 16 h, heure de Francfort)</div>
    <div class="muted" style="font-size:12px;margin-bottom:4px">Performance de la ${ccy} face au ${base==='USD'?'dollar':'euro'} (positif = ${ccy} plus forte)</div>
    <div class="kpis" style="grid-template-columns:repeat(5,1fr)">${cells}</div>`;
}

function renderFX(){
  const ccys = ['EUR', ...Object.keys(S.fx.history.rates)].filter((v,i,a)=>a.indexOf(v)===i);
  const names = {}; for (const c of Object.values(S.atlas.countries)) names[c.currency] = c.name;
  names.EUR = 'Zone euro';
  const opt = sel => ccys.map(c => `<option value="${c}" ${c===sel?'selected':''}>${c} — ${esc(names[c]||'')}</option>`).join('');
  $('#view-fx').innerHTML = `<div class="two">
    <div class="card"><h2>Convertisseur</h2><div class="sub">Taux de référence officiels de la BCE (un fixing par jour ouvré).</div>
      <div class="conv">
        <div><label>Montant</label><input type="number" id="cAmt" value="1000" min="0" step="any"></div><div></div><div></div>
        <div><label>De</label><select id="cFrom">${opt('EUR')}</select></div>
        <div><button class="btn" id="cSwap" title="Inverser">⇄</button></div>
        <div><label>Vers</label><select id="cTo">${opt('USD')}</select></div>
      </div>
      <div class="conv-res" id="cRes"></div><div class="src" id="cInfo"></div>
      <div class="note">Ces taux sont des taux de référence publiés une fois par jour par la BCE, pas des cotations en temps réel. Entre deux fixings, le marché peut bouger : ne pas les utiliser pour traiter.</div>
    </div>
    <div class="card"><h2>Comparateur</h2><div class="sub">Performance de chaque devise face à une devise de base. Positif = la devise s’est appréciée.</div>
      <div class="toolbar"><label class="muted">Base</label><select id="pBase">${opt('USD')}</select></div>
      <div class="tbl-wrap"><table class="t" id="pTbl"></table></div>
      <div class="src" id="pInfo" style="margin-top:8px"></div>
    </div></div>`;
  const conv = () => {
    const a = parseFloat($('#cAmt').value), f=$('#cFrom').value, t=$('#cTo').value;
    const i = lastIdx(k => fxRateAt(f,k) && fxRateAt(t,k));
    if (i<0 || isNaN(a)){ $('#cRes').textContent='n/d'; $('#cInfo').textContent=''; return; }
    const r = cross(f,t,i);
    $('#cRes').innerHTML = `${fmtNum(a, 2)} ${f} = ${fmtNum(a*r, 2)} ${t}`;
    $('#cInfo').innerHTML = `1 ${f} = ${fmtNum(r,6)} ${t} · 1 ${t} = ${fmtNum(1/r,6)} ${f}<br>Source : BCE, taux de référence du ${fmtDate(S.fx.history.dates[i])} (vers 16 h, heure de Francfort). Calcul croisé via l’euro.`;
  };
  ['cAmt','cFrom','cTo'].forEach(id => $('#'+id).oninput = conv);
  $('#cSwap').onclick = () => { const f=$('#cFrom').value; $('#cFrom').value=$('#cTo').value; $('#cTo').value=f; conv(); };
  conv();
  let sortK='ytd', asc=false;
  const table = () => {
    const base = $('#pBase').value;
    const rows = ccys.filter(c=>c!==base).map(c => ({c, p:Object.fromEntries(WINDOWS.map(([,w])=>[w, perf(c,base,w)]))}));
    rows.sort((a,b) => { const x=a.p[sortK], y=b.p[sortK]; if (x==null) return 1; if (y==null) return -1; return asc ? x-y : y-x; });
    const cell = v => { if (v==null) return '<span class="cell faint">n/d</span>'; const t=Math.max(-1,Math.min(1,v/8)); const bg = v>=0 ? `rgba(240,113,90,${Math.abs(t)*.45})` : `rgba(90,169,255,${Math.abs(t)*.45})`; return `<span class="cell" style="background:${bg}">${fmtVal(v,'%',true)}</span>`; };
    $('#pTbl').innerHTML = `<thead><tr><th>Devise</th>${WINDOWS.map(([l,w])=>`<th class="r sortable ${w===sortK?'sorted'+(asc?' asc':''):''}" data-w="${w}">${l}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(r=>`<tr><td><b>${r.c}</b> <span class="faint">${esc(names[r.c]||'')}</span></td>${WINDOWS.map(([,w])=>`<td class="r">${cell(r.p[w])}</td>`).join('')}</tr>`).join('')}</tbody>`;
    $('#pTbl').querySelectorAll('th.sortable').forEach(th => th.onclick = () => { if (sortK===th.dataset.w) asc=!asc; else { sortK=th.dataset.w; asc=false; } table(); });
    const i = lastIdx(k => fxRateAt('USD',k));
    $('#pInfo').innerHTML = `Dernier fixing : ${fmtDate(S.fx.history.dates[i])}. « 1J » = depuis le fixing précédent. Source : ${esc(S.fx.source)} (série ${esc(S.fx.series)}).`;
  };
  $('#pBase').onchange = table; table();
}

// ---------- calendrier ----------
function decText(d){ if (!d) return 'n/d'; return d.type==='hausse'?`<span class="dec hausse">Hausse ${d.bp} pb</span>`:d.type==='baisse'?`<span class="dec baisse">Baisse ${Math.abs(d.bp)} pb</span>`:d.type==='maintien'?'<span class="dec maintien">Maintien</span>':'<span class="faint">non déduite</span>'; }
function renderCalendar(){
  const C = Object.values(S.atlas.countries);
  const next = C.map(c => ({c, d:c.meetings?.next?.date})).sort((a,b) => (a.d||'9999') < (b.d||'9999') ? -1 : 1);
  const last = C.filter(c => c.meetings?.last).sort((a,b) => a.meetings.last.date < b.meetings.last.date ? 1 : -1);
  $('#view-calendar').innerHTML = `<div class="two">
    <div class="card"><h2>Prochaines réunions</h2><div class="sub">Dates de décision tirées des calendriers officiels. « non publiée » : la banque centrale n’a pas encore publié la date.</div>
      <div class="tbl-wrap"><table class="t"><thead><tr><th>Date</th><th></th><th>Banque centrale</th><th class="r">Taux actuel</th><th>Ensuite</th></tr></thead><tbody>
      ${next.map(({c,d}) => `<tr class="click" data-c="${c.code}"><td class="num">${d?fmtDate(d):(c.meetings?.status==='aucun'?'<span class="faint">pas de calendrier</span>':'<span class="faint">non publiée</span>')}</td>
        <td class="count">${d?countdown(d):''}</td><td><b>${esc(c.name)}</b> <span class="faint">${esc(c.cb)}</span> ${badge(c.meetings?.status==='pas_a_jour'?'pas_a_jour':null)}</td>
        <td class="r num">${fmtVal(c.metrics.policy?.value,'%')}</td><td class="faint num">${(c.meetings?.upcoming||[]).slice(1,3).map(fmtDate).join(' · ')}</td></tr>`).join('')}
      </tbody></table></div></div>
    <div class="card"><h2>Dernières décisions</h2><div class="sub">Décision déduite de la série officielle du taux (changement entré en vigueur dans les 10 jours après la réunion).</div>
      <div class="tbl-wrap"><table class="t"><thead><tr><th>Date</th><th>Banque centrale</th><th>Décision</th><th class="r">Nouveau taux</th></tr></thead><tbody>
      ${last.map(c => `<tr class="click" data-c="${c.code}"><td class="num">${fmtDate(c.meetings.last.date)}</td><td><b>${esc(c.name)}</b> <span class="faint">${esc(c.cb)}</span></td>
        <td>${decText(c.meetings.last.decision)}</td><td class="r num">${c.meetings.last.decision?.new!=null?fmtVal(c.meetings.last.decision.new,'%'):'n/d'}</td></tr>`).join('')}
      </tbody></table></div></div></div>`;
  $('#view-calendar').querySelectorAll('tr.click').forEach(tr => tr.onclick = () => select(tr.dataset.c, true));
}

// ---------- classement ----------
function renderRank(){
  let sortK='policy', asc=false;
  const draw = () => {
    const rows = Object.values(S.atlas.countries).sort((a,b) => {
      if (sortK==='name') return asc ? a.name.localeCompare(b.name,'fr') : b.name.localeCompare(a.name,'fr');
      const x=a.metrics[sortK]?.value, y=b.metrics[sortK]?.value; if (x==null) return 1; if (y==null) return -1; return asc ? x-y : y-x; });
    const doms = Object.fromEntries(METRICS.map(m=>[m.key, domain(m.key)]));
    const cell = (k, r) => { const v=r?.value; if (v==null) return '<span class="cell faint">n/d</span>';
      const col = colorFor(k, v, doms[k]); return `<span class="cell" style="background:${col}33;box-shadow:inset 3px 0 0 ${col}" title="${esc([r.date?'valeur du '+fmtDate(r.date):'', STATUS[r.status]||''].filter(Boolean).join(' · '))}">${fmtMetric(k,v)}${r.status&&r.status!=='ok'?' •':''}</span>`; };
    $('#view-rank').innerHTML = `<div class="card"><h2>Classement</h2><div class="sub">Cliquez sur un titre de colonne pour trier, sur une ligne pour ouvrir la fiche. • = valeur ancienne ou pas à jour (survol pour le détail).</div>
      <div class="toolbar"><button class="btn" id="csvBtn">Exporter en CSV</button></div>
      <div class="tbl-wrap"><table class="t"><thead><tr><th class="sortable ${sortK==='name'?'sorted'+(asc?' asc':''):''}" data-k="name">Pays</th>${METRICS.map(m=>`<th class="r sortable ${m.key===sortK?'sorted'+(asc?' asc':''):''}" data-k="${m.key}" title="${esc(m.desc)}">${esc(m.short)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(c=>`<tr class="click" data-c="${c.code}"><td><b>${esc(c.name)}</b> <span class="faint">${c.currency}</span></td>${METRICS.map(m=>`<td class="r">${cell(m.key, c.metrics[m.key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>`;
    $('#view-rank').querySelectorAll('th.sortable').forEach(th => th.onclick = () => { if (sortK===th.dataset.k) asc=!asc; else { sortK=th.dataset.k; asc=th.dataset.k==='name'; } draw(); });
    $('#view-rank').querySelectorAll('tr.click').forEach(tr => tr.onclick = () => select(tr.dataset.c, true));
    $('#csvBtn').onclick = exportCSV;
  };
  draw();
}
function exportCSV(){
  const head = ['pays','banque_centrale','devise', ...METRICS.flatMap(m=>[m.key, m.key+'_date', m.key+'_statut'])];
  const lines = [head.join(';')];
  for (const c of Object.values(S.atlas.countries)) lines.push([c.name, c.cb, c.currency, ...METRICS.flatMap(m => { const r=c.metrics[m.key]||{}; return [r.value==null?'':String(r.value).replace('.',','), r.date||'', r.status||'']; })].map(x=>`"${String(x).replace(/"/g,'""')}"`).join(';'));
  const blob = new Blob(['﻿'+lines.join('\n')], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `fx-atlas-${S.atlas.as_of}.csv`; a.click();
}

// ---------- vue d'ensemble (panneau sans pays) ----------
function overviewHTML(){
  const C = Object.values(S.atlas.countries), m = M[S.metric];
  const soon = C.filter(c => c.meetings?.next?.date && daysTo(c.meetings.next.date)>=0 && daysTo(c.meetings.next.date)<=14).sort((a,b)=>a.meetings.next.date<b.meetings.next.date?-1:1);
  const ranked = C.filter(c => c.metrics[S.metric]?.value!=null).sort((a,b)=>b.metrics[S.metric].value-a.metrics[S.metric].value);
  const ch = S.atlas.changes || [];
  return `<div class="panel-head"><h2>Vue d’ensemble</h2><div class="cb">Cliquez sur un pays du globe pour ouvrir sa fiche.</div></div>
  <div class="panel-body">
    <div class="block"><h3>Ce qui a changé depuis le dernier passage du robot</h3>${ch.length?`<ul class="changes src" style="padding-left:16px;margin:0">${ch.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'<p class="muted" style="margin:0">Aucun changement de taux directeur ni nouvelle publication d’inflation.</p>'}</div>
    <div class="block"><h3>Réunions des 14 prochains jours</h3>${soon.length?`<ul class="list-mini">${soon.map(c=>`<li data-c="${c.code}"><span><b>${esc(c.name)}</b> <span class="faint">${esc(c.cb.split(' (')[0])}</span></span><span class="num">${fmtDate(c.meetings.next.date)} <span class="count">${countdown(c.meetings.next.date)}</span></span></li>`).join('')}</ul>`:'<p class="muted" style="margin:0">Aucune réunion programmée dans les 14 jours.</p>'}</div>
    <div class="block"><h3>${esc(m.label)} — du plus haut au plus bas</h3><ul class="list-mini">${ranked.map(c=>`<li data-c="${c.code}"><span>${esc(c.name)} ${badge(c.metrics[S.metric].status)}</span><span class="num ${m.scale==='div'?signCls(c.metrics[S.metric].value):''}">${fmtMetric(S.metric,c.metrics[S.metric].value)}</span></li>`).join('')}
      ${C.filter(c=>c.metrics[S.metric]?.value==null).map(c=>`<li data-c="${c.code}"><span>${esc(c.name)}</span><span class="faint">n/d</span></li>`).join('')}</ul>
      <p class="src">${esc(m.desc)}</p></div>
  </div>`;
}
function bindOverview(){ $('#panel').querySelectorAll('li[data-c]').forEach(li => li.onclick = () => select(li.dataset.c, true)); }

// ---------- sources & qualité ----------
function renderMethod(){
  const q = S.atlas.quality || {};
  const E = (S.log?.entries || []);
  const bad = E.filter(e => !['OK'].includes(e.statut));
  $('#view-method').innerHTML = `
  <div class="card"><h2>Qualité des données</h2>
    <div class="sub">Dernier passage du robot : ${esc(fmtDateTime(S.atlas.generated_at))}. Le robot tourne chaque jour ; une valeur douteuse n’écrase jamais une bonne valeur.</div>
    <p>${(q.missing||[]).length ? `<span class="st-warn">${q.missing.length} donnée(s) essentielle(s) n/d ou pas à jour :</span> <span class="num faint">${esc(q.missing.join(', '))}</span>` : '<span class="st-ok">Toutes les données essentielles (taux directeur, inflation) sont à jour.</span>'}</p>
    <div class="tbl-wrap"><table class="t"><thead><tr><th>Pays</th><th>Donnée</th><th class="r">Valeur</th><th>Statut</th><th>Source</th><th>Détail</th></tr></thead><tbody>
    ${(bad.length?bad:E).slice(0,200).map(e=>`<tr><td>${esc(e.pays)}</td><td>${esc(e.donnee)}</td><td class="r num">${esc(e.valeur??'n/d')}</td><td class="${e.statut==='OK'?'st-ok':['ERREUR','REFUSÉE','N/D'].includes(e.statut)?'st-bad':'st-warn'}">${esc(e.statut)}</td><td class="faint">${esc(String(e.source).slice(0,70))}</td><td class="faint">${esc(e.detail)}</td></tr>`).join('')}
    </tbody></table></div>
    <p class="src">${bad.length?`Seules les lignes non « OK » sont affichées (${bad.length} sur ${E.length}).`:`Toutes les lignes du journal sont « OK » (${E.length}).`} Journal complet : <a href="data/journal.md" target="_blank">journal.md</a>.</p>
  </div>
  <div class="card"><h2>Sources et définitions</h2><div class="tbl-wrap"><table class="t"><thead><tr><th>Donnée</th><th>Source</th><th>Identifiant</th><th>Fraîcheur</th></tr></thead><tbody>
    <tr><td>Taux directeur</td><td>BIS — taux directeurs des banques centrales ; prioritairement la source de la banque centrale quand elle est interrogée directement (Canada, zone euro, États-Unis)</td><td class="num">WS_CBPOL D.{pays} · Valet V39079 · FM.D.U2.EUR.4F.KR.DFR.LEV · FRED DFEDTARU/DFEDTARL</td><td>quotidienne</td></tr>
    <tr><td>Inflation</td><td>BIS — indices de prix à la consommation nationaux</td><td class="num">WS_LONG_CPI M.{pays}.771</td><td>mensuelle (trimestrielle pour l’Australie et la Nouvelle-Zélande), 1 à 2 mois de décalage</td></tr>
    <tr><td>Taux à 10 ans</td><td>OCDE via FRED (Fed de Saint-Louis)</td><td class="num">IRLTLT01{pays}M156N</td><td>mensuelle</td></tr>
    <tr><td>Taux de change</td><td>BCE — taux de référence</td><td class="num">EXR D.{devise}.EUR.SP00.A</td><td>1 fois par jour ouvré, vers 16 h (Francfort)</td></tr>
    <tr><td>Cible d’inflation</td><td>Site officiel de chaque banque centrale (lien dans la fiche). La mention est revérifiée chaque jour sur la page.</td><td>—</td><td>quotidienne (vérification)</td></tr>
    <tr><td>Dates de réunions</td><td>Calendrier officiel de chaque banque centrale (lien dans la fiche)</td><td>—</td><td>quotidienne</td></tr>
    <tr><td>Dernière décision</td><td>Déduite de la série officielle du taux directeur</td><td>—</td><td>quotidienne</td></tr>
    <tr><td>Dirigeants</td><td>Wikidata (base publique collaborative) — tout changement est signalé dans le journal</td><td class="num">P2388 / P39</td><td>quotidienne</td></tr>
    </tbody></table></div>
    <div class="note"><b>Statuts :</b> « ancienne valeur » = la source n’a rien publié de plus récent ; « pas à jour » = la source n’a pas répondu ou sa nouvelle valeur a été écartée par les contrôles, la dernière valeur validée est affichée avec sa date ; « à vérifier » = la mention de la cible n’a pas été retrouvée sur la page officielle ; « n/d » = aucune valeur fiable.</div>
  </div>`;
}

init();
})();
