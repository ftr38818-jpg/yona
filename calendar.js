/* Read-only adapter inferred from the supplied calendar screenshot.
 * It must pass the diagnostic against the live website before activation.
 * No reservation is clicked and no network request is issued by this adapter.
 */
({target, people}) => {
  const months = ['janvier','fevrier','mars','avril','mai','juin','juillet','aout','septembre','octobre','novembre','decembre'];
  const [year, month, day] = target.split('-').map(Number);
  const normalize = s => (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
  const visible = e => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
  };
  const elements = root => [...root.querySelectorAll('*')].filter(e => !['SCRIPT','STYLE','NOSCRIPT','TEMPLATE'].includes(e.tagName) && visible(e));
  const text = e => normalize(e.innerText);
  const leafMatches = (root, predicate) => {
    const matched = elements(root).filter(e => predicate(text(e)));
    return matched.filter(e => !matched.some(other => other !== e && e.contains(other)));
  };
  const fail = (reason, extra = {}) => ({ready: false, reason, ...extra});
  const busy = [...document.querySelectorAll('[aria-busy="true"], [role="progressbar"]')].some(visible);
  if (busy) return fail('Chargement signale par la page.');
  const counts = leafMatches(document, s => /^\d+ personnes?$/.test(s)).map(e => Number(text(e).split(' ')[0]));
  if (!counts.length || counts.some(n => n !== people)) {
    return fail('Nombre de personnes absent ou different du parametre.', {observed_people: counts});
  }
  const headingRx = new RegExp(`\\b${months[month - 1]}\\s+${year}\\b`);
  const headings = leafMatches(document, s => s.length < 90 && headingRx.test(s));
  if (!headings.length) return fail('Le mois et l\'annee recherches ne sont pas affiches.');
  const numeric = root => leafMatches(root, s => /^(?:[1-9]|[12]\d|3[01])$/.test(s));
  const rowsFor = leaves => {
    const points = leaves.map(e => {
      const r = e.getBoundingClientRect();
      return {e, n: Number(text(e)), x: r.left + r.width / 2, y: r.top + r.height / 2};
    }).sort((a, b) => a.y - b.y || a.x - b.x);
    const rows = [];
    for (const p of points) {
      const last = rows.at(-1);
      if (!last || Math.abs(p.y - last[0].y) > 10) rows.push([p]); else last.push(p);
    }
    return rows.map(r => r.sort((a,b) => a.x - b.x));
  };
  let grid = null, root = null;
  for (const h of headings) {
    for (let candidate = h.parentElement; candidate && candidate !== document.body; candidate = candidate.parentElement) {
      const ns = numeric(candidate);
      if (ns.length < 28 || ns.length > 42) continue;
      const rows = rowsFor(ns);
      if (rows.length < 4 || rows.length > 6 || rows.some(r => r.length !== 7)) continue;
      const header = text(candidate).replace(/\./g, '');
      if (!/(?:\blu ma me je ve sa di\b|\blun mar mer jeu ven sam dim\b|\blundi mardi mercredi jeudi vendredi samedi dimanche\b)/.test(header)) continue;
      const first = new Date(Date.UTC(year, month - 1, 1));
      first.setUTCDate(1 - (first.getUTCDay() + 6) % 7);
      const flat = rows.flat();
      let valid = true;
      for (let i = 0; i < flat.length; i++) {
        const d = new Date(first); d.setUTCDate(first.getUTCDate() + i);
        flat[i].date = d.toISOString().slice(0, 10);
        if (flat[i].n !== d.getUTCDate()) { valid = false; break; }
        if (Math.abs(flat[i].x - rows[0][i % 7].x) > 12) { valid = false; break; }
      }
      if (valid && flat.some(p => p.date === target)) { grid = flat; root = candidate; break; }
    }
    if (grid) break;
  }
  if (!grid) return fail('Grille non reconnue : impossible d\'associer sans ambiguite chaque numero a une date.');
  const dx = Math.abs(grid[1].x - grid[0].x), dy = Math.abs(grid[7].y - grid[0].y);
  const cellFor = point => {
    let e = point.e;
    while (e.parentElement && e.parentElement !== root) {
      const parent = e.parentElement, r = parent.getBoundingClientRect();
      if (r.width > dx * 1.7 || r.height > dy * 1.7 || grid.filter(p => parent.contains(p.e)).length !== 1) break;
      e = parent;
    }
    return e;
  };
  const rgb = s => {
    const m = s.match(/^rgba?\(\s*(\d+(?:\.\d+)?)\s*[, ]\s*(\d+(?:\.\d+)?)\s*[, ]\s*(\d+(?:\.\d+)?)(?:\s*[,/]\s*([\d.]+))?\s*\)$/);
    return m && (!m[4] || Number(m[4]) > 0.5) ? m.slice(1,4).map(Number) : null;
  };
  const kindOf = c => {
    if (!c) return null;
    const [r,g,b] = c;
    if (g >= 80 && g-r >= 20 && g-b >= 15) return 'Day';
    if (b >= 100 && b-r >= 35 && b >= g-30) return 'Night';
    return null;
  };
  const markers = container => {
    const found = [];
    const record = (color, width, height) => {
      const c = rgb(color), kind = kindOf(c);
      if (kind && width >= 2 && height >= 2 && width <= 20 && height <= 20 && width/height < 2.5 && height/width < 2.5) found.push({kind, color:c});
    };
    for (const e of [container, ...elements(container)]) {
      if (!visible(e)) continue;
      const r = e.getBoundingClientRect(), s = getComputedStyle(e);
      record(s.backgroundColor, r.width, r.height);
      if (/^[\u2022\u25cf\u25cb]$/.test((e.innerText || '').trim())) record(s.color, r.width, r.height);
      if (e.tagName.toLowerCase() === 'circle') record(s.fill, r.width, r.height);
      for (const pseudo of ['::before','::after']) {
        const ps = getComputedStyle(e, pseudo);
        if (ps.content !== 'none' && ps.content !== 'normal' && ps.display !== 'none' && ps.visibility !== 'hidden' && ps.opacity !== '0') {
          record(ps.backgroundColor, parseFloat(ps.width), parseFloat(ps.height));
        }
      }
    }
    return found;
  };
  const legend = {};
  for (const kind of ['Day','Night']) {
    const labels = leafMatches(document, s => s === `${kind.toLowerCase()} spa disponible`);
    for (const label of labels) {
      for (let e = label, depth = 0; e && depth < 4; e = e.parentElement, depth++) {
        if (e.contains(root)) break;
        const match = markers(e).find(m => m.kind === kind);
        if (match) { legend[kind] = match.color; break; }
      }
      if (legend[kind]) break;
    }
  }
  if (!legend.Day || !legend.Night) return fail('Les deux legendes colorees ne sont pas reconnues.');
  const matching = cell => [...new Set(markers(cell).filter(m => legend[m.kind].every((v,i) => Math.abs(v-m.color[i]) <= 24)).map(m => m.kind))].sort();
  const cells = grid.map(p => {
    const el = cellFor(p);
    const relevant = [el, ...elements(el)];
    const disabled = relevant.some(e => e.hasAttribute('disabled') || e.getAttribute('aria-disabled') === 'true' || /(?:^|\s)(?:disabled|unavailable|unselectable|ui-state-disabled|ui-datepicker-unselectable|not-available)(?:\s|$)/i.test(e.getAttribute('class') || ''));
    return {date: p.date, day: p.n, offers: matching(el), disabled, element: el};
  });
  const selected = cells.find(c => c.date === target);
  if (selected.offers.length && selected.disabled) return fail('Signaux contradictoires : point colore et case desactivee.');
  if (!selected.offers.length && !selected.disabled && !cells.some(c => c.offers.length)) {
    return fail('Aucun marqueur reconnu dans la grille : chargement incomplet ou structure modifiee.');
  }
  const safeHTML = el => {
    const clone = el.cloneNode(true);
    for (const child of [...clone.querySelectorAll('script,style,input,textarea,iframe')]) child.remove();
    for (const child of [clone, ...clone.querySelectorAll('*')]) {
      for (const attr of [...child.attributes]) {
        if (!['class','role','aria-disabled','disabled'].includes(attr.name)) child.removeAttribute(attr.name);
      }
    }
    return clone.outerHTML.slice(0, 16000);
  };
  return {
    ready: true, target, people, offers: selected.offers,
    status: selected.offers.length ? 'available' : 'unavailable',
    evidence: selected.offers.length ? 'Marqueur(s) de couleur correspondant a la legende.' : selected.disabled ? 'Case explicitement desactivee.' : 'Pas de marqueur dans la case ; marqueurs reconnus ailleurs dans la grille.',
    target_cell_html: safeHTML(selected.element),
    days: cells.map(({element, ...rest}) => rest),
    legend,
  };
}
