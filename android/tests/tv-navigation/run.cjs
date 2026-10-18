/*
 * Tests des scripts injectés par l'appli Android (navigation TV + pont Retour),
 * dans un vrai Chromium : c'est le moteur du WebView d'Android.
 *
 * Lancement (Playwright doit être installé, voir android/README.md) :
 *   NODE_PATH=<dossier node_modules contenant playwright> node android/tests/tv-navigation/run.cjs
 * Code retour 0 si tout passe, 1 sinon (utilisé par la CI).
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const ASSETS = path.join(__dirname, '..', '..', 'app', 'src', 'main', 'assets') + path.sep;
const script = fs.readFileSync(ASSETS + 'arrmada-bridge.js', 'utf8') + '\n' +
  fs.readFileSync(ASSETS + 'tv-navigation.js', 'utf8').replace('__ARRMADA_TV_WIDTH__', '1280');
let failed = 0;
function check(name, cond, extra) { console.log((cond ? 'OK  ' : 'FAIL') + ' ' + name + (cond ? '' : ' -> ' + JSON.stringify(extra))); if (!cond) failed++; }
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
  page.on('pageerror', e => { console.log('PAGEERROR', e.message); failed++; });
  await page.addInitScript(script);                     // = addDocumentStartJavaScript
  await page.goto('file://' + path.join(__dirname, 'page.html'));
  const active = () => page.evaluate(() => document.activeElement && (document.activeElement.id || document.activeElement.tagName));
  check('viewport imposé', (await page.evaluate(() => document.querySelector('meta[name=viewport]').content)) === 'width=1280');
  check('style injecté', await page.evaluate(() => !!document.getElementById('arrmada-tv-style')));
  // ré-injection (repli onPageFinished) : aucune erreur, pas de double écouteur
  await page.evaluate(script);
  await page.keyboard.press('ArrowDown'); const first = await active();
  check('premier appui -> premier élément en haut', first === 'n0' || first === 'g00', first);
  await page.focus('#g00'); await page.keyboard.press('ArrowRight'); check('droite 00->01', (await active()) === 'g01', await active());
  await page.keyboard.press('ArrowDown'); check('bas 01->11', (await active()) === 'g11', await active());
  await page.keyboard.press('ArrowLeft'); check('gauche 11->10', (await active()) === 'g10', await active());
  await page.keyboard.press('ArrowLeft'); const side = await active(); check('gauche 10->menu latéral', /^n\d$/.test(side), side);
  check('liseré de focus', await page.evaluate(() => document.activeElement.classList.contains('arrmada-tv-focus')));
  await page.focus('#g22'); await page.keyboard.press('ArrowDown'); check('bas depuis grille -> champ', (await active()) === 'field', await active());
  // champ : curseur à la fin -> gauche reste dans le champ
  await page.evaluate(() => { const f = document.getElementById('field'); f.setSelectionRange(3, 3); });
  await page.keyboard.press('ArrowLeft'); check('gauche dans le champ (curseur bouge)', (await active()) === 'field' && (await page.evaluate(() => document.getElementById('field').selectionStart)) === 2);
  await page.evaluate(() => document.getElementById('field').setSelectionRange(0, 0));
  await page.keyboard.press('ArrowUp'); check('haut sort du champ', (await active()) !== 'field', await active());
  // OK sur champ : demande le clavier si fermé
  await page.evaluate(() => { window.kb = 0; window.ArrMadaAndroid = { isKeyboardVisible: () => false, showKeyboard: () => { window.kb++; } }; });
  await page.focus('#field'); await page.keyboard.press('Enter'); check('OK sur champ -> clavier demandé', (await page.evaluate(() => window.kb)) === 1);
  await page.evaluate(() => { window.ArrMadaAndroid.isKeyboardVisible = () => true; });
  await page.keyboard.press('Enter'); check('clavier ouvert -> pas de nouvelle demande', (await page.evaluate(() => window.kb)) === 1);
  // OK sur div role=button -> click
  await page.focus('#card'); await page.keyboard.press('Enter'); check('OK sur role=button -> click', (await page.evaluate(() => clicked.includes('card'))));
  // composant qui gère ses flèches : on ne bouge pas
  await page.focus('#widget'); await page.keyboard.press('ArrowDown'); check('widget garde la flèche', (await active()) === 'widget' && (await page.evaluate(() => clicked.includes('widget-down'))));
  // élément lointain : défilement au lieu de saut
  await page.focus('#card'); await page.keyboard.press('ArrowDown'); // -> widget (proche)
  const y0 = await page.evaluate(() => scrollY); await page.evaluate(() => document.getElementById('card').focus());
  await page.evaluate(() => document.getElementById('widget').remove());
  await page.keyboard.press('ArrowDown'); await page.waitForTimeout(600);
  check('cible lointaine -> défilement, pas de saut (conteneur tabindex=-1 ignoré)', (await active()) === 'card' && (await page.evaluate(() => scrollY)) > y0, { a: await active(), y: await page.evaluate(() => scrollY) });
  // Pont Retour : modale qui se ferme sur Échap
  await page.evaluate(() => {
    const d = document.createElement('div'); d.setAttribute('role', 'dialog'); d.setAttribute('data-state', 'open'); d.id = 'dlg';
    d.innerHTML = '<button id="in1">a</button><button id="in2">b</button>'; d.style.cssText = 'position:fixed;top:100px;left:300px;width:300px;height:100px;background:#fff';
    document.body.appendChild(d);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') { const x = document.getElementById('dlg'); x && x.remove(); } });
  });
  await page.focus('#in1'); await page.keyboard.press('ArrowRight'); check('navigation limitée à la modale', (await active()) === 'in2', await active());
  check('Retour ferme la modale', (await page.evaluate(() => window.__arrmadaBack())) === true && (await page.evaluate(() => !document.getElementById('dlg'))));
  check('Retour sans modale -> false', (await page.evaluate(() => window.__arrmadaBack())) === false);
  // modale qui ignore Échap : 2e Retour rend la main
  await page.evaluate(() => { const d = document.createElement('div'); d.setAttribute('role', 'dialog'); d.setAttribute('data-state', 'open'); d.id='stuck'; document.body.appendChild(d); });
  const b1 = await page.evaluate(() => window.__arrmadaBack()); const b2 = await page.evaluate(() => window.__arrmadaBack());
  check('modale sourde à Échap -> 2e Retour rendu à l\'appli', b1 === true && b2 === false, [b1, b2]);
  await browser.close();
  console.log(failed ? `${failed} échec(s)` : 'TOUS LES TESTS OK'); process.exit(failed ? 1 : 0);
})();
