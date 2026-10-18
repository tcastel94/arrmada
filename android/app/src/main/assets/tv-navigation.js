/*
 * ArrMada Android TV — piloter la web app à la télécommande (flèches + OK).
 *
 * Injecté par MainActivity dans chaque page du serveur ArrMada, sur TV
 * seulement, avant le code de la page. La web app n'est pas modifiée : ce
 * script ajoute par-dessus ce qu'il manque à un navigateur sans souris.
 *
 *  1. Largeur d'affichage : une TV 1080p se présente comme un écran de 960 px.
 *     On impose une largeur plus confortable (réglage de l'écran de connexion ;
 *     la valeur de VIEWPORT_WIDTH est écrite par MainActivity).
 *  2. Focus visible : liseré bleu #4A9EFF autour de l'élément sélectionné.
 *  3. Flèches : déplacent le focus vers l'élément cliquable le plus proche dans
 *     la direction demandée (« navigation spatiale », comme sur un lanceur TV).
 *     S'il n'y a rien dans cette direction, la page défile.
 *  4. OK : active l'élément sélectionné ; sur un champ de saisie, ouvre le
 *     clavier à l'écran.
 *
 * Les composants qui gèrent déjà les flèches eux-mêmes (menus, listes
 * déroulantes, curseurs de la web app) ne sont pas touchés : ils marquent la
 * touche comme traitée (event.defaultPrevented) et ce script s'efface.
 */
(function () {
  'use strict';
  if (window.__arrmadaTv) return;
  window.__arrmadaTv = true;

  var VIEWPORT_WIDTH = __ARRMADA_TV_WIDTH__;
  var FOCUS_CLASS = 'arrmada-tv-focus';

  // ─── 1 + 2. Largeur d'affichage et style du focus ──────────────────────────

  function applyViewport() {
    var head = document.head;
    if (!head) return;
    var wanted = 'width=' + VIEWPORT_WIDTH;
    var meta = head.querySelector('meta[name="viewport"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.setAttribute('name', 'viewport');
      head.appendChild(meta);
    }
    if (meta.getAttribute('content') !== wanted) meta.setAttribute('content', wanted);
  }

  function applyStyle() {
    if (!document.head || document.getElementById('arrmada-tv-style')) return;
    var style = document.createElement('style');
    style.id = 'arrmada-tv-style';
    style.textContent =
      '.' + FOCUS_CLASS + ' {' +
      ' outline: 3px solid #4A9EFF !important;' +
      ' outline-offset: 3px !important;' +
      ' box-shadow: 0 0 0 7px rgba(74, 158, 255, 0.28) !important;' +
      ' border-radius: 8px;' +
      '}';
    document.head.appendChild(style);
  }

  var headObserved = false;
  function setup() {
    applyViewport();
    applyStyle();
    // La web app peut réécrire l'en-tête en changeant de page : on surveille
    // l'en-tête seulement (pas toute la page, ce serait coûteux).
    if (!headObserved && document.head && window.MutationObserver) {
      headObserved = true;
      new MutationObserver(function () {
        applyViewport();
        applyStyle();
      }).observe(document.head, { childList: true, subtree: true, attributes: true, attributeFilter: ['content'] });
    }
  }

  // Le script tourne avant que la page existe : on attend l'en-tête.
  if (document.head) setup();
  document.addEventListener('DOMContentLoaded', setup);

  // Le liseré suit le focus, quelle que soit la façon dont il est arrivé.
  document.addEventListener('focusin', function (event) {
    var el = event.target;
    if (el && el.classList && el !== document.body) el.classList.add(FOCUS_CLASS);
  }, true);
  document.addEventListener('focusout', function (event) {
    var el = event.target;
    if (el && el.classList) el.classList.remove(FOCUS_CLASS);
  }, true);

  // ─── 3. Navigation aux flèches ─────────────────────────────────────────────

  var FOCUSABLE = [
    'a[href]', 'button', 'input:not([type="hidden"])', 'select', 'textarea', 'summary',
    '[tabindex]', '[contenteditable="true"]',
    '[role="button"]', '[role="link"]', '[role="tab"]', '[role="switch"]', '[role="checkbox"]',
    '[role="radio"]', '[role="slider"]', '[role="option"]', '[role="menuitem"]'
  ].join(',');

  // tabindex="-1" signifie « focusable par script seulement » (conteneurs,
  // pièges à focus) : ignoré, sauf pour les vrais contrôles qui le portent.
  var INTERACTIVE_ROLE = /^(button|link|tab|switch|checkbox|radio|slider|option|menuitem)/;

  var KEY_DIRECTIONS = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' };

  function isShown(el) {
    var rect = el.getBoundingClientRect();
    if (rect.width < 4 || rect.height < 4) return false;
    var style = window.getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';
  }

  function isCandidate(el) {
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
    if (el.getAttribute('tabindex') === '-1' && !INTERACTIVE_ROLE.test(el.getAttribute('role') || '')) return false;
    // Une modale ouverte marque le reste de la page aria-hidden / inert.
    if (el.closest('[aria-hidden="true"], [inert]')) return false;
    return isShown(el);
  }

  /** Zone de navigation : la fenêtre ouverte au premier plan, sinon toute la page. */
  function scopeRoot() {
    var layers = document.querySelectorAll('[role="dialog"], [role="alertdialog"], [aria-modal="true"]');
    for (var i = layers.length - 1; i >= 0; i--) {
      if (isShown(layers[i])) return layers[i];
    }
    return document;
  }

  function candidates() {
    var nodes = scopeRoot().querySelectorAll(FOCUSABLE);
    var list = [];
    for (var i = 0; i < nodes.length; i++) {
      if (isCandidate(nodes[i])) list.push(nodes[i]);
    }
    return list;
  }

  function center(rect) {
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  }

  // Écart entre deux segments [a1,a2] et [b1,b2] (0 s'ils se chevauchent).
  function gap(a1, a2, b1, b2) {
    return Math.max(0, Math.max(a1, b1) - Math.min(a2, b2));
  }

  /**
   * Meilleur élément dans la direction demandée. Score = distance dans l'axe
   * + 4 × décalage sur l'autre axe : dans une grille d'affiches, « droite »
   * choisit la voisine de la même rangée avant celle de la rangée du dessous.
   */
  function best(from, dir, list) {
    var a = from.getBoundingClientRect();
    var ac = center(a);
    var winner = null;
    var winnerScore = Infinity;
    var winnerDistance = 0;
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (el === from || el.contains(from)) continue;
      var b = el.getBoundingClientRect();
      var bc = center(b);
      var main;
      var cross;
      var crossCenter;
      if (dir === 'right') {
        if (bc.x <= ac.x + 1 || b.right <= a.right) continue;
        main = Math.max(0, b.left - a.right);
        cross = gap(a.top, a.bottom, b.top, b.bottom);
        crossCenter = Math.abs(bc.y - ac.y);
      } else if (dir === 'left') {
        if (bc.x >= ac.x - 1 || b.left >= a.left) continue;
        main = Math.max(0, a.left - b.right);
        cross = gap(a.top, a.bottom, b.top, b.bottom);
        crossCenter = Math.abs(bc.y - ac.y);
      } else if (dir === 'down') {
        if (bc.y <= ac.y + 1 || b.bottom <= a.bottom) continue;
        main = Math.max(0, b.top - a.bottom);
        cross = gap(a.left, a.right, b.left, b.right);
        crossCenter = Math.abs(bc.x - ac.x);
      } else {
        if (bc.y >= ac.y - 1 || b.top >= a.top) continue;
        main = Math.max(0, a.top - b.bottom);
        cross = gap(a.left, a.right, b.left, b.right);
        crossCenter = Math.abs(bc.x - ac.x);
      }
      var score = main + cross * 4 + crossCenter * 0.1;
      if (score < winnerScore) {
        winnerScore = score;
        winner = el;
        winnerDistance = main;
      }
    }
    return winner ? { el: winner, distance: winnerDistance } : null;
  }

  /** Premier élément visible à l'écran (en haut à gauche) : point de départ. */
  function firstOnScreen(list) {
    var height = window.innerHeight;
    var pick = null;
    var pickRect = null;
    for (var i = 0; i < list.length; i++) {
      var r = list[i].getBoundingClientRect();
      if (r.bottom < 0 || r.top > height) continue;
      if (!pick || r.top < pickRect.top - 4 || (Math.abs(r.top - pickRect.top) <= 4 && r.left < pickRect.left)) {
        pick = list[i];
        pickRect = r;
      }
    }
    return pick || list[0] || null;
  }

  /** Conteneur qui défile autour de l'élément (la web app a ses propres zones de défilement). */
  function scroller(el) {
    var node = el && el.parentElement;
    while (node && node !== document.body && node !== document.documentElement) {
      var overflowY = window.getComputedStyle(node).overflowY;
      if ((overflowY === 'auto' || overflowY === 'scroll') && node.scrollHeight > node.clientHeight + 4) {
        return node;
      }
      node = node.parentElement;
    }
    return document.scrollingElement || document.documentElement;
  }

  function scrollPage(dir, from) {
    if (dir !== 'up' && dir !== 'down') return;
    var amount = Math.round(window.innerHeight * 0.4) * (dir === 'down' ? 1 : -1);
    scroller(from).scrollBy({ top: amount, behavior: 'smooth' });
  }

  function focusElement(el, vertical) {
    try {
      el.focus({ preventScroll: true });
    } catch (e) {
      el.focus();
    }
    // Élément cliquable sans focus natif (ex. <div role="button">) : on le rend focusable.
    if (document.activeElement !== el) {
      el.setAttribute('tabindex', '-1');
      el.focus({ preventScroll: true });
    }
    // On ne fait défiler que si l'élément sort de la zone confortable :
    // sinon l'écran bougerait à chaque appui.
    var r = el.getBoundingClientRect();
    var margin = 80;
    var offScreen = r.top < margin || r.bottom > window.innerHeight - margin ||
      r.left < 0 || r.right > window.innerWidth;
    if (offScreen) {
      el.scrollIntoView({ block: vertical ? 'center' : 'nearest', inline: 'nearest', behavior: 'smooth' });
    }
  }

  function move(dir) {
    var list = candidates();
    if (!list.length) {
      scrollPage(dir, document.activeElement);
      return;
    }
    var active = document.activeElement;
    if (!active || active === document.body || list.indexOf(active) === -1) {
      var start = firstOnScreen(list);
      if (start) focusElement(start, true);
      return;
    }
    var found = best(active, dir, list);
    var vertical = dir === 'up' || dir === 'down';
    // Rien dans cette direction, ou prochain élément très loin (long texte
    // sans bouton) : on fait défiler pour laisser lire, sans sauter.
    if (!found || (vertical && found.distance > window.innerHeight * 0.8)) {
      scrollPage(dir, active);
      return;
    }
    focusElement(found.el, vertical);
  }

  // ─── Champs de saisie ──────────────────────────────────────────────────────

  var TEXT_TYPES = /^(text|search|url|email|password|number|tel)$/;

  function isTextField(el) {
    if (!el) return false;
    if (el.tagName === 'TEXTAREA' || el.isContentEditable) return true;
    return el.tagName === 'INPUT' && TEXT_TYPES.test(el.type || 'text');
  }

  /**
   * Dans un champ, gauche/droite déplacent le curseur dans le texte ; on ne
   * sort du champ qu'arrivé au bord (début ou fin du texte). Dans une zone de
   * texte multiligne, haut/bas aussi.
   */
  function keepArrowInField(el, dir) {
    if (!isTextField(el)) return false;
    if (el.isContentEditable) return dir === 'left' || dir === 'right';
    var start;
    var end;
    try {
      start = el.selectionStart;
      end = el.selectionEnd;
    } catch (e) {
      return false; // type sans curseur lisible (email, number) : on navigue
    }
    if (start === null || start === undefined) return false;
    var length = (el.value || '').length;
    var multiline = el.tagName === 'TEXTAREA';
    if (dir === 'left') return start > 0;
    if (dir === 'right') return end < length;
    if (dir === 'up') return multiline && start > 0;
    return multiline && end < length;
  }

  function nativeBridge() {
    return window.ArrMadaAndroid || null;
  }

  // Éléments que la touche OK (Entrée) active déjà nativement.
  function activatesNatively(el) {
    var tag = el.tagName;
    if (tag === 'INPUT') return !/^(checkbox|radio)$/.test(el.type);
    return tag === 'A' || tag === 'BUTTON' || tag === 'SELECT' || tag === 'TEXTAREA' || tag === 'SUMMARY';
  }

  // ─── Touches ───────────────────────────────────────────────────────────────

  // Écoute en dernier (sur window, phase de remontée) : les composants de la
  // page ont déjà eu la touche et l'ont marquée traitée s'ils s'en occupent.
  window.addEventListener('keydown', function (event) {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
    var active = document.activeElement;
    var dir = KEY_DIRECTIONS[event.key];

    if (dir) {
      if (keepArrowInField(active, dir)) return;
      event.preventDefault();
      move(dir);
      return;
    }

    if (event.key !== 'Enter' || !active || active === document.body) return;

    // OK sur un champ : ouvre le clavier à l'écran s'il est fermé. S'il est
    // ouvert, Entrée vient du clavier (« OK / Aller ») : on laisse valider.
    if (isTextField(active)) {
      var bridge = nativeBridge();
      if (bridge && !bridge.isKeyboardVisible()) {
        event.preventDefault();
        bridge.showKeyboard();
      }
      return;
    }

    if (!activatesNatively(active)) {
      event.preventDefault();
      active.click();
    }
  }, false);
})();
