// Rührwerk – Oberfläche. Kein Framework, keine Abhängigkeiten.
// Sicherheit: Rezeptdaten kommen aus dem Internet. Darum wird nie innerHTML benutzt,
// sondern nur textContent bzw. Textknoten (Hilfsfunktion h()).

const app = document.getElementById('app');
const timerLeiste = document.getElementById('timer-leiste');
const navSlot = document.getElementById('nav-slot');

// ---------- Hilfsfunktionen ----------
function h(tag, props = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const kind of kinder.flat(Infinity)) {
    if (kind == null || kind === false) continue;
    e.append(kind);
  }
  return e;
}

// Wie app.replaceChildren, aber ohne null/false: replaceChildren(null) würde sonst das Wort "null" anzeigen.
function anzeigen(...kinder) {
  app.replaceChildren(...kinder.flat(Infinity).filter((k) => k != null && k !== false));
}

const zahl = (n) => new Intl.NumberFormat('de-DE', { maximumFractionDigits: 2 }).format(n);

function dauerText(s) {
  const std = Math.floor(s / 3600);
  const min = Math.floor((s % 3600) / 60);
  const sek = Math.round((s % 60) * 10) / 10;
  const teile = [];
  if (std) teile.push(`${std} Std.`);
  if (min) teile.push(`${min} Min.`);
  if (sek || !teile.length) teile.push(`${zahl(sek)} Sek.`);
  return teile.join(' ');
}

function uhrText(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, '0')}`;
}

async function api(pfad, optionen = {}) {
  let antwort;
  try {
    antwort = await fetch(pfad, optionen);
  } catch {
    throw new Error('Keine Verbindung zu Rührwerk. Bitte prüfe, ob der Server läuft und du im richtigen WLAN bist.');
  }
  if (!antwort.ok) {
    let detail = `Fehler ${antwort.status}`;
    try {
      const d = await antwort.json();
      if (typeof d.detail === 'string') detail = d.detail;
      else if (Array.isArray(d.detail)) detail = d.detail.map((x) => String(x.msg).replace(/^Value error, /, '')).join(' ');
    } catch { /* Antwort war kein JSON */ }
    throw new Error(detail);
  }
  return antwort.status === 204 ? null : antwort.json();
}

const sendeJson = (methode, daten) => ({
  method: methode,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(daten),
});

function speicherLesen(schluessel) {
  try { return localStorage.getItem(schluessel); } catch { return null; }
}
function speicherSchreiben(schluessel, wert) {
  try { localStorage.setItem(schluessel, wert); } catch { /* z. B. privater Modus */ }
}

// ---------- Beschreibung einer Einstellung ----------
function stufeText(e) {
  switch (e.art) {
    case 'stufe': return `Stufe ${zahl(e.stufe)}`;
    case 'sanftruehr': return 'Sanftrührstufe';
    case 'teigknet': return 'Teigknetstufe';
    case 'turbo': return 'Turbo';
    default: return null;
  }
}

function einstellungWerte(e) {
  const werte = [];
  if (e.dauer_s != null) werte.push(['Zeit', (e.wiederholungen > 1 ? `${e.wiederholungen}× ` : '') + dauerText(e.dauer_s)]);
  if (e.varoma) werte.push(['Temperatur', 'Varoma']);
  else if (e.temperatur_c != null) werte.push(['Temperatur', `${zahl(e.temperatur_c)} °C`]);
  const stufe = stufeText(e);
  if (stufe) werte.push(['Drehzahl', stufe]);
  if (e.linkslauf) werte.push(['Richtung', 'Linkslauf']);
  return werte;
}

// ---------- Zustand ----------
let rezeptZwischenspeicher = {}; // slug -> aufbereitetes Rezept
let zeichenNummer = 0; // verwirft veraltete Antworten, wenn man schnell weiternavigiert

async function rezeptHolen(slug, frisch = false) {
  if (!frisch && rezeptZwischenspeicher[slug]) return rezeptZwischenspeicher[slug];
  const r = await api(`/api/rezepte/${encodeURIComponent(slug)}`);
  rezeptZwischenspeicher[slug] = r;
  return r;
}

function portionenFaktor(r) {
  if (!r.portionen) return 1;
  const gewuenscht = Number(speicherLesen(`ruehrwerk.portionen.${r.slug}`)) || r.portionen;
  return gewuenscht / r.portionen;
}

function zutatText(z, faktor) {
  if (z.menge == null) return z.anzeige + (faktor !== 1 && /\d/.test(z.anzeige) ? ' (Menge nicht umgerechnet)' : '');
  const teile = [`${zahl(z.menge * faktor)}`, z.einheit, z.name].filter(Boolean).join(' ');
  return z.notiz ? `${teile}, ${z.notiz}` : teile;
}

// ---------- Wake Lock (Bildschirm bleibt an) ----------
// Mit HTTPS gibt es die Wake-Lock-Schnittstelle. Ohne HTTPS (z. B. http://192.168.x.x im Heimnetz) spielen wir
// stattdessen ein winziges, stummes Video ab: Solange Video läuft, schaltet das Handy den Bildschirm meist nicht aus.
let wachSperre = null;
let wachGewuenscht = false;
let wachVideo = null;
// Safari am iPhone erlaubt Video nur direkt nach einer Berührung: darum bei jeder Berührung im Kochmodus erneut starten.
function wachStatus(laeuft) {
  const e = document.getElementById('wach-status');
  if (e) e.textContent = laeuft
    ? 'Bildschirm bleibt an (Ersatztrick läuft).'
    : 'Tippe einmal auf den Bildschirm, damit er anbleibt.';
}
document.addEventListener('pointerdown', () => {
  if (wachGewuenscht && wachVideo && wachVideo.paused) videoErsatz(true);
}, { passive: true });
function videoErsatz(an) {
  if (an) {
    if (!wachVideo) {
      const v = h('video', { muted: '', loop: '', playsinline: '', 'aria-hidden': 'true', tabindex: '-1', preload: 'auto' },
        h('source', { src: 'wach.mp4', type: 'video/mp4' }), h('source', { src: 'wach.webm', type: 'video/webm' }));
      v.muted = true; // muss als Eigenschaft gesetzt sein, sonst blockieren Browser das Abspielen
      v.style.cssText = 'position:fixed;left:0;bottom:0;width:4px;height:4px;opacity:0.05;pointer-events:none';
      document.body.append(v);
      wachVideo = v;
    }
    wachVideo.play().then(() => wachStatus(true), () => wachStatus(false));
  } else if (wachVideo) {
    wachVideo.pause();
  }
}
async function wachHalten(an) {
  wachGewuenscht = an;
  if (!('wakeLock' in navigator)) { videoErsatz(an); return; }
  try {
    if (an && !wachSperre) {
      wachSperre = await navigator.wakeLock.request('screen');
      wachSperre.addEventListener('release', () => { wachSperre = null; });
    } else if (!an && wachSperre) {
      await wachSperre.release();
      wachSperre = null;
    }
  } catch { if (an) videoErsatz(true); /* z. B. Akkusparmodus: dann Ersatz versuchen */ }
}
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && wachGewuenscht && !wachSperre) wachHalten(true);
});

// ---------- Timer ----------
const timer = []; // { id, label, ende, fertig }
let timerNr = 0;
let ton = null;
let alarmIntervall = null;

function tonFreischalten() {
  try {
    ton = ton || new (window.AudioContext || window.webkitAudioContext)();
    if (ton.state === 'suspended') ton.resume();
  } catch { /* kein Ton möglich */ }
}

function piepen() {
  try {
    if (!ton) return;
    for (let i = 0; i < 3; i++) {
      const o = ton.createOscillator();
      const g = ton.createGain();
      o.frequency.value = 880;
      g.gain.value = 0.25;
      o.connect(g).connect(ton.destination);
      const t0 = ton.currentTime + i * 0.35;
      o.start(t0);
      o.stop(t0 + 0.22);
    }
  } catch { /* ignorieren */ }
  if (navigator.vibrate) navigator.vibrate([300, 150, 300]);
}

function timerStarten(label, sekunden) {
  tonFreischalten();
  timer.push({ id: ++timerNr, label, ende: Date.now() + sekunden * 1000, fertig: false });
  timerZeichnen();
}

function timerEntfernen(id) {
  const i = timer.findIndex((t) => t.id === id);
  if (i >= 0) timer.splice(i, 1);
  if (!timer.some((t) => t.fertig) && alarmIntervall) { clearInterval(alarmIntervall); alarmIntervall = null; }
  timerZeichnen();
}

function timerZeichnen() {
  timerLeiste.replaceChildren(
    ...timer.map((t) =>
      h('div', { class: `timer${t.fertig ? ' fertig' : ''}`, role: t.fertig ? 'alert' : null },
        h('div', {},
          h('div', { class: 'klein' }, t.label),
          h('div', { class: 'rest', 'data-timer': t.id }, t.fertig ? 'Abgelaufen!' : uhrText(t.ende - Date.now())),
        ),
        h('button', { class: 'knopf', type: 'button', onclick: () => timerEntfernen(t.id), 'aria-label': `Timer ${t.label} ${t.fertig ? 'beenden' : 'abbrechen'}` }, t.fertig ? 'OK' : 'Stopp'),
      ),
    ),
  );
}

setInterval(() => {
  let neuZeichnen = false;
  for (const t of timer) {
    if (t.fertig) continue;
    if (Date.now() >= t.ende) {
      t.fertig = true;
      neuZeichnen = true;
      piepen();
      if (!alarmIntervall) alarmIntervall = setInterval(piepen, 4000);
    } else {
      const feld = timerLeiste.querySelector(`[data-timer="${t.id}"]`);
      if (feld) feld.textContent = uhrText(t.ende - Date.now());
    }
  }
  if (neuZeichnen) timerZeichnen();
}, 250);

// Höhe der unteren Leiste messen, damit nichts davon verdeckt wird
const untenFeld = document.getElementById('unten');
new ResizeObserver(() => {
  document.documentElement.style.setProperty('--unten-h', `${untenFeld.offsetHeight}px`);
}).observe(untenFeld);

// ---------- Dialog: Einstellung prüfen / ändern ----------
const TEMPERATUREN = [null, 37, ...Array.from({ length: 17 }, (_, i) => 40 + i * 5), 'varoma'];
const STUFEN = [0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const ARTEN = [['stufe', 'Stufe'], ['sanftruehr', 'Sanftrühr'], ['teigknet', 'Teigknet'], ['turbo', 'Turbo'], ['keine', 'Keine']];

function naechster(liste, wert, richtung) {
  // Liefert das Nachbarelement; liegt der Wert nicht in der Liste, springt es zum nächsten gültigen.
  const i = liste.indexOf(wert);
  if (i >= 0) return liste[Math.min(liste.length - 1, Math.max(0, i + richtung))];
  const zahlen = liste.filter((x) => typeof x === 'number');
  if (richtung > 0) return zahlen.find((x) => x > wert) ?? zahlen[zahlen.length - 1];
  return [...zahlen].reverse().find((x) => x < wert) ?? zahlen[0];
}

function dauerSchritt(s, richtung) {
  const schritt = s < 60 || (s === 60 && richtung < 0) ? 5 : s < 600 ? 30 : 60;
  return Math.max(1, s + richtung * schritt);
}

function pruefDialog(slug, schritt, e, danach) {
  const werte = {
    dauer_s: e.dauer_s, temperatur_c: e.temperatur_c, varoma: e.varoma, stufe: e.stufe,
    art: e.art, linkslauf: e.linkslauf, wiederholungen: e.wiederholungen,
  };
  const anzeigen = [];
  const aktualisieren = () => anzeigen.forEach((f) => f());

  const stepper = (name, anzeige, minus, plus, sichtbar = () => true) => {
    const ausgabe = h('output', { 'aria-live': 'polite' });
    const zeile = h('div', { class: 'stepper' },
      h('span', { class: 'name' }, name),
      h('div', { class: 'steuerung' },
        h('button', { class: 'knopf', type: 'button', 'aria-label': `${name} verringern`, onclick: () => { minus(); aktualisieren(); } }, '−'),
        ausgabe,
        h('button', { class: 'knopf', type: 'button', 'aria-label': `${name} erhöhen`, onclick: () => { plus(); aktualisieren(); } }, '+'),
      ),
    );
    anzeigen.push(() => { ausgabe.textContent = anzeige(); zeile.hidden = !sichtbar(); });
    return zeile;
  };

  const tempWert = () => (werte.varoma ? 'varoma' : werte.temperatur_c);
  const tempSetzen = (w) => { werte.varoma = w === 'varoma'; werte.temperatur_c = typeof w === 'number' ? w : null; };

  const dialog = h('dialog', { 'aria-labelledby': 'dlg-titel' },
    h('h2', { id: 'dlg-titel' }, 'Einstellung prüfen'),
    h('p', {}, 'Im Rezept steht: ', h('q', {}, e.text)),
    e.hinweise.length ? h('ul', { class: 'einst-hinweise' }, e.hinweise.map((x) => h('li', {}, x.text))) : null,
    h('p', { class: 'leise klein' }, 'Stelle ein, was du am Gerät einstellen willst, und tippe auf „Bestätigen“.'),
    stepper('Zeit',
      () => (werte.dauer_s == null ? 'keine' : dauerText(werte.dauer_s)),
      () => { werte.dauer_s = werte.dauer_s == null ? 60 : dauerSchritt(werte.dauer_s, -1); },
      () => { werte.dauer_s = werte.dauer_s == null ? 60 : dauerSchritt(werte.dauer_s, 1); }),
    stepper('Temperatur',
      () => { const t = tempWert(); return t === 'varoma' ? 'Varoma' : t == null ? 'aus' : `${zahl(t)} °C`; },
      () => tempSetzen(naechster(TEMPERATUREN, tempWert() ?? null, -1)),
      () => tempSetzen(naechster(TEMPERATUREN, tempWert() ?? null, 1))),
    h('fieldset', {},
      h('legend', {}, 'Drehzahl'),
      h('div', { class: 'auswahl' }, ARTEN.map(([wert, text]) =>
        h('label', {},
          h('input', { type: 'radio', name: 'art', value: wert, checked: werte.art === wert, onchange: () => { werte.art = wert; if (wert === 'stufe' && werte.stufe == null) werte.stufe = 1; aktualisieren(); } }),
          h('span', {}, text)))),
    ),
    stepper('Stufe',
      () => (werte.stufe == null ? '–' : zahl(werte.stufe)),
      () => { werte.stufe = naechster(STUFEN, werte.stufe ?? 1, -1); },
      () => { werte.stufe = naechster(STUFEN, werte.stufe ?? 1, 1); },
      () => werte.art === 'stufe'),
    h('label', { class: 'schalter' },
      h('input', { type: 'checkbox', checked: werte.linkslauf, onchange: (ev) => { werte.linkslauf = ev.target.checked; } }),
      'Linkslauf'),
    h('p', { class: 'fehler-text', role: 'alert', hidden: true }),
    h('div', { class: 'knopf-zeile' },
      h('button', { class: 'knopf haupt', type: 'button', onclick: async (ev) => {
        const knopf = ev.currentTarget;
        knopf.disabled = true;
        knopf.textContent = 'Speichere …';
        try {
          const korrekt = { ...werte, stufe: werte.art === 'stufe' ? werte.stufe : null };
          await api(`/api/rezepte/${encodeURIComponent(slug)}/schritte/${encodeURIComponent(schritt.id)}/einstellungen/${e.nr}`, sendeJson('PUT', { werte: korrekt }));
          dialog.close();
          await danach();
        } catch (fehler) {
          knopf.disabled = false;
          knopf.textContent = 'Bestätigen';
          const feld = dialog.querySelector('.fehler-text');
          feld.hidden = false;
          feld.textContent = `Das hat nicht geklappt: ${fehler.message}`;
        }
      } }, 'Bestätigen'),
      h('button', { class: 'knopf', type: 'button', onclick: () => dialog.close() }, 'Abbrechen'),
    ),
  );
  dialog.addEventListener('close', () => dialog.remove());
  document.body.append(dialog);
  aktualisieren();
  dialog.showModal();
}

// Bestätigt die erkannten Werte unverändert ("Passt so")
async function direktBestaetigen(slug, schritt, e) {
  const werte = {
    dauer_s: e.dauer_s, temperatur_c: e.temperatur_c, varoma: e.varoma, stufe: e.stufe,
    art: e.art, linkslauf: e.linkslauf, wiederholungen: e.wiederholungen,
  };
  await api(`/api/rezepte/${encodeURIComponent(slug)}/schritte/${encodeURIComponent(schritt.id)}/einstellungen/${e.nr}`, sendeJson('PUT', { werte }));
}

// ---------- Ansicht: Startseite ----------
async function startAnsicht(nr) {
  navSlot.replaceChildren();
  wachHalten(false);
  document.title = 'Rührwerk';

  const chip = h('span', { class: 'status-chip', role: 'status' }, 'Verbindung nicht geprüft');
  const pruefen = async () => {
    chip.className = 'status-chip';
    chip.textContent = 'Prüfe Verbindung …';
    try {
      const info = await api('/api/verbindung-testen', { method: 'POST' });
      chip.className = 'status-chip ok';
      chip.textContent = `Mealie ${info.version ?? ''} verbunden`;
    } catch (fehler) {
      chip.className = 'status-chip fehler';
      chip.textContent = 'Mealie nicht verbunden';
      chip.title = fehler.message;
    }
  };

  const importFehler = h('p', { id: 'import-fehler', class: 'klein', role: 'alert', style: 'color: var(--fehler); margin: 4px 0 0' });
  const eingabe = h('input', { id: 'link', type: 'url', inputmode: 'url', autocomplete: 'off', autocapitalize: 'off', spellcheck: 'false', placeholder: 'https://…', 'aria-describedby': 'import-fehler' });
  const knopf = h('button', { class: 'knopf haupt', type: 'submit' }, 'Importieren');

  const formular = h('form', { novalidate: true, onsubmit: async (ev) => {
    ev.preventDefault();
    importFehler.textContent = '';
    eingabe.removeAttribute('aria-invalid');
    const url = eingabe.value.trim();
    if (!/^https?:\/\/\S+$/i.test(url)) {
      eingabe.setAttribute('aria-invalid', 'true');
      importFehler.textContent = 'Bitte einen Link einfügen, der mit http:// oder https:// beginnt.';
      eingabe.focus();
      return;
    }
    if (/cookidoo/i.test(new URL(url).hostname)) {
      eingabe.setAttribute('aria-invalid', 'true');
      importFehler.textContent = 'Links zu Cookidoo werden nicht unterstützt. Nutze einen frei zugänglichen Rezept-Link, ein Foto aus deinem eigenen Kochbuch oder füge den Text selbst ein.';
      return;
    }
    knopf.disabled = true;
    knopf.textContent = 'Importiere … (das kann etwas dauern)';
    try {
      const { slug } = await api('/api/import', sendeJson('POST', { url }));
      location.hash = `#/rezept/${encodeURIComponent(slug)}`;
    } catch (fehler) {
      knopf.disabled = false;
      knopf.textContent = 'Importieren';
      eingabe.setAttribute('aria-invalid', 'true');
      importFehler.textContent = `Import nicht möglich: ${fehler.message} Prüfe den Link oder versuche es später noch einmal.`;
    }
  } },
    h('label', { for: 'link' }, 'Rezept-Link einfügen'),
    h('div', { class: 'feld-zeile' }, eingabe, knopf),
    importFehler,
  );


  // ---- Foto / Text per KI (Mealie liest das Rezept) ----
  const MAX_BILDER = 6;
  const MAX_MB = 10;
  let gewaehlt = [];
  const kiFehler = h('p', { id: 'ki-fehler', class: 'klein', role: 'alert', style: 'color: var(--fehler); margin: 4px 0 0' });
  const kiListe = h('ul', { class: 'foto-liste' });
  const kiDatei = h('input', { id: 'ki-fotos', type: 'file', accept: 'image/*', multiple: true, class: 'nur-lesen' });
  const kiWaehlen = h('label', { for: 'ki-fotos', class: 'knopf', role: 'button', tabindex: '0' }, 'Foto aufnehmen oder auswählen');
  const kiText = h('textarea', { id: 'ki-text', rows: '4', maxlength: '20000', placeholder: 'Zum Beispiel: Rezept hier einfügen oder eine Korrektur schreiben' });
  const kiKnopf = h('button', { class: 'knopf haupt', type: 'submit', disabled: true }, 'Mit KI einlesen');
  const kiAktualisieren = () => {
    kiListe.replaceChildren(...gewaehlt.map((datei, i) => h('li', {},
      h('span', {}, `Seite ${i + 1}: ${datei.name || 'Foto'} (${(datei.size / 1048576).toFixed(1).replace('.', ',')} MB)`),
      h('button', { class: 'knopf', type: 'button', 'aria-label': `Seite ${i + 1} entfernen`, onclick: () => { gewaehlt.splice(i, 1); kiAktualisieren(); } }, 'Entfernen'))));
    kiKnopf.disabled = !(gewaehlt.length || kiText.value.trim());
  };
  kiDatei.addEventListener('change', () => {
    kiFehler.textContent = '';
    for (const f of kiDatei.files) {
      if (gewaehlt.length >= MAX_BILDER) { kiFehler.textContent = `Höchstens ${MAX_BILDER} Fotos auf einmal.`; break; }
      if (f.size > MAX_MB * 1048576) { kiFehler.textContent = `„${f.name}“ ist größer als ${MAX_MB} MB.`; continue; }
      gewaehlt.push(f);
    }
    kiDatei.value = ''; // damit man dasselbe Foto oder weitere Seiten erneut wählen kann
    kiAktualisieren();
  });
  kiWaehlen.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); kiDatei.click(); } });
  kiText.addEventListener('input', kiAktualisieren);

  const kiFormular = h('form', { novalidate: true, hidden: true, onsubmit: async (ev) => {
    ev.preventDefault();
    kiFehler.textContent = '';
    const daten = new FormData();
    gewaehlt.forEach((f) => daten.append('bilder', f, f.name || 'foto.jpg'));
    if (kiText.value.trim()) daten.append('text', kiText.value.trim());
    kiKnopf.disabled = true;
    kiKnopf.textContent = 'KI liest das Rezept … (bis zu 2 Minuten)';
    try {
      const { slug } = await api('/api/import-ki', { method: 'POST', body: daten });
      location.hash = `#/rezept/${encodeURIComponent(slug)}`;
    } catch (fehler) {
      kiFehler.textContent = `Einlesen nicht möglich: ${fehler.message.replace(/[.!?]?$/, '.')} Ist in Mealie unter Gruppeneinstellungen ein KI-Anbieter als Standard-Anbieter eingerichtet?`;
    } finally {
      kiKnopf.textContent = 'Mit KI einlesen';
      kiAktualisieren();
    }
  } },
    h('p', { class: 'klein leise' }, 'Fotografiere ein Rezept (mehrere Seiten möglich). Die Fotos gehen über Mealie an deinen KI-Anbieter. Bitte nur eigene Rezepte für den privaten Gebrauch. Die KI kann sich irren: Prüfe Mengen und Einstellungen.'),
    kiWaehlen, kiDatei, kiListe,
    h('details', {}, h('summary', {}, 'Text oder Notiz ergänzen (optional)'), h('label', { for: 'ki-text', class: 'nur-lesen' }, 'Text oder Notiz'), kiText),
    kiKnopf, kiFehler,
  );

  const reiter = (text, zeigeKi) => h('button', { type: 'button', class: 'reiter', 'aria-pressed': String(zeigeKi === false), onclick: (ev) => {
    formular.hidden = zeigeKi; kiFormular.hidden = !zeigeKi;
    ev.currentTarget.parentElement.querySelectorAll('.reiter').forEach((b) => b.setAttribute('aria-pressed', String(b === ev.currentTarget)));
  } }, text);
  const reiterZeile = h('div', { class: 'reiter-zeile', role: 'group', 'aria-label': 'Art des Imports' }, reiter('Link', false), reiter('Foto / Text', true));

  const liste = h('ul', { class: 'karte-liste' });
  const listenStatus = h('div', {});
  const suche = h('input', { id: 'suche', type: 'search', placeholder: 'Rezepte durchsuchen …', autocomplete: 'off', 'aria-label': 'Rezepte durchsuchen' });
  let seite = 1;
  let zeitgeber = null;

  const rezepteLaden = async (anhaengen = false) => {
    if (!anhaengen) { seite = 1; liste.replaceChildren(); }
    listenStatus.replaceChildren(h('p', { class: 'laden' }, 'Lade Rezepte …'));
    try {
      const daten = await api(`/api/rezepte?suche=${encodeURIComponent(suche.value.trim())}&seite=${seite}`);
      if (nr !== zeichenNummer) return;
      liste.append(...daten.rezepte.map((r) =>
        h('li', {}, h('a', { class: 'rezept-karte', href: `#/rezept/${encodeURIComponent(r.slug)}` },
          r.hat_bild ? h('img', { src: `/api/bild/${r.id}?datei=tiny-original.webp`, alt: '', loading: 'lazy', width: 64, height: 64 }) : h('div', { class: 'platzhalter', 'aria-hidden': 'true' }),
          h('span', {}, r.name)))));
      listenStatus.replaceChildren();
      if (!liste.children.length) {
        listenStatus.append(h('p', { class: 'leise' }, suche.value.trim() ? 'Keine Rezepte gefunden.' : 'Noch keine Rezepte. Füge oben einen Link ein, dann erscheint das Rezept hier.'));
      } else if (daten.seite < daten.seiten) {
        listenStatus.append(h('button', { class: 'knopf', type: 'button', onclick: () => { seite += 1; rezepteLaden(true); } }, 'Mehr laden'));
      }
    } catch (fehler) {
      if (nr !== zeichenNummer) return;
      listenStatus.replaceChildren(
        h('div', { class: 'meldung fehler', role: 'alert' }, fehler.message,
          h('p', { class: 'klein' }, 'Läuft Mealie? Prüfe außerdem die Adresse und den API-Token in der Konfiguration (Datei .env).')),
        h('button', { class: 'knopf', type: 'button', onclick: () => rezepteLaden(anhaengen) }, 'Erneut versuchen'));
    }
  };
  suche.addEventListener('input', () => { clearTimeout(zeitgeber); zeitgeber = setTimeout(() => rezepteLaden(), 300); });

  const titel = h('h1', { tabindex: '-1' }, 'Rührwerk');
  anzeigen(
    h('header', { class: 'kopf' }, titel, chip),
    h('p', { class: 'leise' }, 'Deine Rezepte aus Mealie – Schritt für Schritt zum Nachkochen. Kompatibel mit Thermomix®.'),
    h('section', { 'aria-labelledby': 'import-titel' },
      h('h2', { id: 'import-titel' }, 'Neues Rezept'),
      reiterZeile, formular, kiFormular),
    h('section', { 'aria-labelledby': 'rezepte-titel' },
      h('h2', { id: 'rezepte-titel' }, 'Meine Rezepte'),
      h('label', { for: 'suche', class: 'nur-lesen' }, 'Rezepte durchsuchen'),
      suche, liste, listenStatus),
    h('p', { class: 'fuss klein leise' },
      'Importierte Rezepte nur für den privaten Gebrauch. „Thermomix“ ist eine Marke der Vorwerk International & Co. KmG; Rührwerk steht in keiner Verbindung zu Vorwerk.'),
  );
  titel.focus({ preventScroll: true });
  pruefen();
  rezepteLaden();
}

// ---------- Ansicht: Rezept ----------
async function rezeptAnsicht(slug, nr, neuGeladen = false) {
  navSlot.replaceChildren();
  wachHalten(false);
  if (!neuGeladen) anzeigen(h('p', { class: 'laden' }, 'Lade Rezept …'));
  let r;
  try {
    r = await rezeptHolen(slug, true);
  } catch (fehler) {
    if (nr !== zeichenNummer) return;
    anzeigen(
      h('a', { class: 'link', href: '#/' }, '← Alle Rezepte'),
      h('div', { class: 'meldung fehler', role: 'alert' }, fehler.message),
      h('button', { class: 'knopf', type: 'button', onclick: () => rezeptAnsicht(slug, nr) }, 'Erneut versuchen'));
    return;
  }
  if (nr !== zeichenNummer) return;
  document.title = `${r.name} – Rührwerk`;

  // Nach dem Bestätigen neu laden, aber an derselben Stelle bleiben (sonst springt die Seite nach oben)
  const neuLaden = async () => {
    const y = window.scrollY;
    await rezeptAnsicht(slug, ++zeichenNummer, true);
    window.scrollTo(0, y);
  };

  const portionenAus = h('output', { 'aria-live': 'polite', id: 'portionen-wert' });
  const zutatenListe = h('ul', { class: 'zutaten' });
  const zutatenZeichnen = () => {
    const faktor = portionenFaktor(r);
    if (r.portionen) portionenAus.textContent = zahl(r.portionen * faktor);
    zutatenListe.replaceChildren(...r.zutaten.map((z) => h('li', { class: z.titel && !z.anzeige ? 'titel' : null }, z.titel && !z.anzeige ? z.titel : zutatText(z, faktor))));
  };
  const portionenAendern = (richtung) => {
    const aktuell = r.portionen * portionenFaktor(r);
    const neu = Math.max(1, Math.min(99, Math.round(aktuell) + richtung));
    speicherSchreiben(`ruehrwerk.portionen.${slug}`, String(neu));
    zutatenZeichnen();
  };

  const offene = r.schritte.flatMap((s, i) => s.einstellungen.filter((e) => e.status === 'pruefen').map((e) => ({ s, i, e })));
  const pruefBereich = offene.length
    ? h('section', { 'aria-labelledby': 'pruef-titel' },
        h('h2', { id: 'pruef-titel' }, `${offene.length} ${offene.length === 1 ? 'Angabe' : 'Angaben'} bitte prüfen`),
        h('p', { class: 'leise' }, 'Diese Werte sind unsicher. Tippe auf „Passt so“ oder ändere sie – nichts wird stillschweigend übernommen.'),
        h('div', { class: 'pruefen-liste' }, offene.map(({ s, i, e }) =>
          h('div', { class: 'pruef-karte' },
            h('p', {}, `Schritt ${i + 1}: `, h('q', {}, e.text)),
            h('ul', {}, e.hinweise.map((x) => h('li', {}, x.text))),
            h('div', { class: 'knopf-zeile' },
              h('button', { class: 'knopf haupt', type: 'button', onclick: async (ev) => {
                ev.currentTarget.disabled = true;
                try { await direktBestaetigen(slug, s, e); await neuLaden(); } catch (f) { ev.currentTarget.disabled = false; alert(f.message); }
              } }, 'Passt so'),
              h('button', { class: 'knopf', type: 'button', onclick: () => pruefDialog(slug, s, e, neuLaden) }, 'Ändern'))))))
    : null;

  anzeigen(
    h('a', { class: 'link', href: '#/' }, '← Alle Rezepte'),
    r.hat_bild ? h('img', { class: 'rezept-bild', src: `/api/bild/${r.id}`, alt: `Foto: ${r.name}` }) : null,
    h('h1', { tabindex: '-1', id: 'rezept-titel' }, r.name),
    r.beschreibung ? h('p', { class: 'leise' }, r.beschreibung) : null,
    h('a', { class: 'knopf haupt gross', href: `#/kochen/${encodeURIComponent(slug)}/0`, 'aria-disabled': r.schritte.length ? null : 'true' }, 'Kochen starten'),
    r.ki_gelesen ? h('p', { class: 'meldung warnung', role: 'note' }, 'Dieses Rezept hat die KI aus einem Foto gelesen. Sie kann Zahlen verwechseln (zum Beispiel 6 und 8). Vergleiche Zeiten, Temperaturen und Stufen mit dem Foto oben und bestätige sie.') : null,
    r.offen ? h('p', { class: 'klein leise' }, `${r.offen} ungeprüfte ${r.offen === 1 ? 'Angabe ist' : 'Angaben sind'} im Kochmodus markiert.`) : null,
    pruefBereich,
    h('h2', {}, 'Zutaten'),
    r.portionen ? h('div', { class: 'portionen', role: 'group', 'aria-label': 'Portionen' },
      h('span', {}, 'Portionen:'),
      h('button', { class: 'knopf', type: 'button', 'aria-label': 'Eine Portion weniger', onclick: () => portionenAendern(-1) }, '−'),
      portionenAus,
      h('button', { class: 'knopf', type: 'button', 'aria-label': 'Eine Portion mehr', onclick: () => portionenAendern(1) }, '+'),
    ) : null,
    r.portionen ? h('p', { class: 'klein leise' }, 'Hinweis: Nur die Zutatenmengen werden umgerechnet. Zeiten und Einstellungen im Rezept bleiben wie angegeben.') : null,
    r.zutaten.length ? zutatenListe : h('p', { class: 'leise' }, 'Zu diesem Rezept gibt es keine Zutatenliste.'),
    !r.schritte.length ? h('div', { class: 'meldung warnung' }, r.schritte_gesperrt
      ? 'Keine Zubereitungsschritte gefunden. Die Seite zeigt die Schritte vermutlich nur Mitgliedern. Importiere das Rezept stattdessen als Foto oder Text.'
      : 'Dieses Rezept hat noch keine Schritte. Ergänze sie in Mealie.') : null,
  );
  zutatenZeichnen();
  if (!neuGeladen) document.getElementById('rezept-titel').focus({ preventScroll: true });
}

// ---------- Ansicht: Kochmodus ----------
function textMitMarkierung(text, einstellungen) {
  // Die Positionen vom Server zählen Zeichen (Unicode-Codepunkte), JavaScript zählt UTF-16 – darum Array.from.
  const zeichen = Array.from(text);
  const teile = [];
  let pos = 0;
  for (const e of [...einstellungen].sort((a, b) => a.start - b.start)) {
    if (e.start < pos) continue;
    if (e.start > pos) teile.push(zeichen.slice(pos, e.start).join(''));
    teile.push(h('mark', { class: 'einst-markiert' }, zeichen.slice(e.start, e.ende).join('')));
    pos = e.ende;
  }
  if (pos < zeichen.length) teile.push(zeichen.slice(pos).join(''));
  return teile;
}

async function kochAnsicht(slug, index, nr) {
  let r;
  try {
    r = await rezeptHolen(slug);
  } catch (fehler) {
    if (nr !== zeichenNummer) return;
    anzeigen(h('div', { class: 'meldung fehler', role: 'alert' }, fehler.message), h('a', { class: 'link', href: '#/' }, '← Zur Startseite'));
    return;
  }
  if (nr !== zeichenNummer) return;
  const gesamt = r.schritte.length;
  if (!gesamt) { location.replace(`#/rezept/${encodeURIComponent(slug)}`); return; }
  index = Math.min(Math.max(index, 0), gesamt - 1);
  const s = r.schritte[index];
  document.title = `Schritt ${index + 1}/${gesamt} – ${r.name}`;
  wachHalten(true);

  const gehe = (i) => { location.replace(`#/kochen/${encodeURIComponent(slug)}/${i}`); window.scrollTo(0, 0); };
  const faktor = portionenFaktor(r);
  const neuLaden = async () => { await rezeptHolen(slug, true); kochAnsicht(slug, index, ++zeichenNummer); };

  const einstKarten = s.einstellungen.map((e) => {
    const pruefen = e.status === 'pruefen';
    return h('div', { class: `einst${pruefen ? ' pruefen' : ''}` },
      h('div', { class: 'einst-werte' }, einstellungWerte(e).map(([etikett, wert]) =>
        h('div', { class: 'wert' }, h('span', { class: 'etikett' }, etikett), h('span', { class: 'zahl' }, wert)))),
      pruefen ? h('ul', { class: 'einst-hinweise' }, e.hinweise.map((x) => h('li', {}, x.text))) : null,
      h('div', { class: 'knopf-zeile' },
        e.dauer_s != null && !pruefen ? h('button', { class: 'knopf haupt', type: 'button', onclick: () => timerStarten(`Schritt ${index + 1} · ${dauerText(e.dauer_s)}`, e.dauer_s) }, `Timer ${dauerText(e.dauer_s)}`) : null,
        pruefen ? h('button', { class: 'knopf haupt', type: 'button', onclick: async (ev) => { ev.currentTarget.disabled = true; try { await direktBestaetigen(slug, s, e); await neuLaden(); } catch (f) { ev.currentTarget.disabled = false; alert(f.message); } } }, 'Passt so') : null,
        h('button', { class: pruefen ? 'knopf' : 'knopf leise-knopf', type: 'button', onclick: () => pruefDialog(slug, s, e, neuLaden) }, 'Ändern'),
      ));
  });

  const zeitKnoepfe = s.zeiten.map((z) =>
    h('button', { class: 'knopf', type: 'button', onclick: () => timerStarten(`Schritt ${index + 1} · ${dauerText(z.dauer_s)}`, z.dauer_s) },
      `Timer ${dauerText(z.dauer_s)}${z.dauer_max_s ? ` bis ${dauerText(z.dauer_max_s)}` : ''}`));

  const zutatenDiesesSchritts = r.zutaten.filter((z) => z.id && s.zutaten.includes(z.id));

  anzeigen(
    h('div', { class: 'koch-kopf' },
      h('a', { class: 'knopf', href: `#/rezept/${encodeURIComponent(slug)}` }, '✕ Beenden'),
      h('span', { class: 'leise', role: 'status' }, `Schritt ${index + 1} von ${gesamt}`)),
    h('div', { class: 'fortschritt', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': gesamt, 'aria-valuenow': index + 1, 'aria-label': 'Fortschritt' },
      h('div', { style: `width:${((index + 1) / gesamt) * 100}%` })),
    s.titel ? h('p', { class: 'abschnitt' }, s.titel) : null,
    h('h1', { class: 'nur-lesen', tabindex: '-1', id: 'schritt-titel' }, `Schritt ${index + 1}`),
    einstKarten.length ? h('div', { class: 'chips' }, einstKarten) : null,
    h('p', { class: 'schritt-text' }, textMitMarkierung(s.text, s.einstellungen)),
    zeitKnoepfe.length ? h('div', { class: 'knopf-zeile' }, zeitKnoepfe) : null,
    zutatenDiesesSchritts.length ? h('section', { class: 'schritt-zutaten', 'aria-labelledby': 'sz-titel' },
      h('h2', { id: 'sz-titel' }, 'Zutaten für diesen Schritt'),
      h('ul', {}, zutatenDiesesSchritts.map((z) => h('li', {}, zutatText(z, faktor))))) : null,
    !('wakeLock' in navigator) ? h('p', { class: 'klein leise', id: 'wach-status', role: 'status' }, wachVideo && !wachVideo.paused ? 'Bildschirm bleibt an (Ersatztrick läuft).' : 'Tippe einmal auf den Bildschirm, damit er anbleibt.') : null,
  );

  navSlot.replaceChildren(h('nav', { class: 'nav', 'aria-label': 'Schritte' },
    h('button', { class: 'knopf gross', type: 'button', disabled: index === 0, onclick: () => gehe(index - 1) }, '← Zurück'),
    index < gesamt - 1
      ? h('button', { class: 'knopf haupt gross', type: 'button', onclick: () => gehe(index + 1) }, 'Weiter →')
      : h('a', { class: 'knopf haupt gross', href: `#/rezept/${encodeURIComponent(slug)}` }, 'Fertig ✓')));

  kochSteuerung = { zurueck: () => index > 0 && gehe(index - 1), weiter: () => index < gesamt - 1 && gehe(index + 1) };
  document.getElementById('schritt-titel').focus({ preventScroll: true });
}

// Wischen und Pfeiltasten im Kochmodus
let kochSteuerung = null;
let wischStart = null;
document.addEventListener('touchstart', (ev) => {
  wischStart = ev.touches.length === 1 && !ev.target.closest('dialog, button, a, input') ? { x: ev.touches[0].clientX, y: ev.touches[0].clientY } : null;
}, { passive: true });
document.addEventListener('touchend', (ev) => {
  if (!wischStart || !kochSteuerung || document.querySelector('dialog[open]')) return;
  const dx = ev.changedTouches[0].clientX - wischStart.x;
  const dy = ev.changedTouches[0].clientY - wischStart.y;
  wischStart = null;
  if (Math.abs(dx) > 70 && Math.abs(dy) < 50) (dx < 0 ? kochSteuerung.weiter : kochSteuerung.zurueck)();
}, { passive: true });
document.addEventListener('keydown', (ev) => {
  if (!kochSteuerung || ev.target.closest('input, textarea, dialog')) return;
  if (ev.key === 'ArrowRight') kochSteuerung.weiter();
  if (ev.key === 'ArrowLeft') kochSteuerung.zurueck();
});

// ---------- Routing ----------
function route() {
  const nr = ++zeichenNummer;
  kochSteuerung = null;
  const teile = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent);
  if (!teile.length) return startAnsicht(nr);
  if (teile[0] === 'rezept' && teile[1]) return rezeptAnsicht(teile[1], nr);
  if (teile[0] === 'kochen' && teile[1]) return kochAnsicht(teile[1], parseInt(teile[2] ?? '0', 10) || 0, nr);
  location.replace('#/');
}
window.addEventListener('hashchange', route);
route();

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => { /* ohne Offline-Hilfe weiterarbeiten */ });
}
