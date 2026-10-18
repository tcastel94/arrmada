/*
 * ArrMada Android — pont entre l'appli et la page web (téléphone, tablette, TV).
 *
 * Injecté par MainActivity dans chaque page du serveur ArrMada, avant le code
 * de la page. Peut être exécuté plusieurs fois : la garde ci-dessous l'ignore.
 *
 * window.__arrmadaBack() — appelée à chaque appui sur la touche Retour d'Android.
 *   Si une fenêtre est ouverte dans la page (modale, menu, liste déroulante),
 *   elle est fermée comme avec la touche Échap d'un clavier, et la fonction
 *   renvoie true. Sinon elle renvoie false et l'appli gère le Retour
 *   (page précédente, ou menu de l'appli sur la première page).
 */
(function () {
  'use strict';
  if (window.__arrmadaBridge) return;
  window.__arrmadaBridge = true;

  // Fenêtres ouvertes des composants Radix de la web app (Dialog, Popover,
  // DropdownMenu, Select) : elles portent toutes data-state="open".
  var OPEN_LAYERS = [
    '[role="dialog"][data-state="open"]',
    '[role="alertdialog"][data-state="open"]',
    '[role="menu"][data-state="open"]',
    '[role="listbox"][data-state="open"]'
  ].join(',');

  // Dernière fenêtre à qui on a envoyé Échap. Si elle est toujours là au
  // Retour suivant, c'est qu'elle ignore Échap : on rend la main à l'appli
  // au lieu de bloquer l'utilisateur.
  var lastLayer = null;

  window.__arrmadaBack = function () {
    var layers = document.querySelectorAll(OPEN_LAYERS);
    if (!layers.length) {
      lastLayer = null;
      return false;
    }
    var top = layers[layers.length - 1];
    if (top === lastLayer && document.contains(top)) {
      lastLayer = null;
      return false;
    }
    lastLayer = top;
    var target = document.activeElement || document.body;
    target.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true
    }));
    return true;
  };
})();
