// Rôle : l'« unité d'écran » (u) qui fait grandir l'affichage avec la taille
// de la tablette ; utilisée par tous les panneaux de l'écran.

/* ══════════════════════════════════════════════════════════════
   2. Affichage — lisible depuis le canapé
   ══════════════════════════════════════════════════════════════
   La tablette est lue à 3-4 m. Les tailles ne sont donc pas en pixels mais
   en « unités d'écran » (u), une variable CSS (--u) :
     - paysage : 1 u = le plus petit de 1 % de la hauteur et 0,625 % de la
       largeur → 8 px sur la Pixel Tablet (1280 × 800), 10,8 px sur un PC
       en 1920 × 1080 ;
     - portrait : 1 u = le plus petit de 0,625 % de la hauteur et 1 % de la
       largeur → 8 px sur la tablette tournée, ~3,9 px sur un téléphone.
   La même page remplit n'importe quel écran sans déborder, un peu comme
   un volume LVM en 100%FREE qui prend toute la place disponible.

   Pendant une lecture : l'affiche sur toute la hauteur, l'heure de FIN en
   très grand, puis le début, le reste et la barre de progression. Rien
   d'autre (les téléchargements et sorties attendent la fin du film).
   Au repos : grande horloge, sorties à venir, téléchargements, ampli.
   ══════════════════════════════════════════════════════════════ */

/** Taille en unités d'écran : u(26) → « calc(var(--u) * 26) ». */
export const u = (n: number) => `calc(var(--u) * ${n})`;
