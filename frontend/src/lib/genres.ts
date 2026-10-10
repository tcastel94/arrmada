/**
 * Traduction d'affichage des genres.
 * ----------------------------------------------------------------
 * Radarr / Sonarr / TMDB renvoient les genres en anglais. On ne traduit
 * QUE l'affichage : la valeur d'origine reste utilisée pour les filtres
 * envoyés à l'API (sinon le filtre « Drame » ne trouverait rien).
 */
const GENRES_FR: Record<string, string> = {
    action: "Action",
    "action & adventure": "Action & aventure",
    adventure: "Aventure",
    animation: "Animation",
    anime: "Anime",
    biography: "Biographie",
    children: "Jeunesse",
    comedy: "Comédie",
    crime: "Policier",
    documentary: "Documentaire",
    drama: "Drame",
    family: "Famille",
    fantasy: "Fantastique",
    "film-noir": "Film noir",
    "game show": "Jeu télévisé",
    history: "Histoire",
    horror: "Horreur",
    kids: "Jeunesse",
    "martial arts": "Arts martiaux",
    music: "Musique",
    musical: "Comédie musicale",
    mystery: "Mystère",
    news: "Actualités",
    reality: "Téléréalité",
    "reality-tv": "Téléréalité",
    romance: "Romance",
    "sci-fi & fantasy": "SF & fantastique",
    "science fiction": "Science-fiction",
    "science-fiction": "Science-fiction",
    "sci-fi": "Science-fiction",
    soap: "Feuilleton",
    sport: "Sport",
    "suspense": "Suspense",
    "talk show": "Talk-show",
    "talk": "Talk-show",
    thriller: "Thriller",
    "tv movie": "Téléfilm",
    war: "Guerre",
    "war & politics": "Guerre & politique",
    western: "Western",
    "mini-series": "Mini-série",
};

/** "Drama" → "Drame" (genre inconnu → renvoyé tel quel). */
export function translateGenre(genre: string): string {
    return GENRES_FR[genre.trim().toLowerCase()] ?? genre;
}
