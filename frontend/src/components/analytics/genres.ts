/**
 * Traduction des genres. Radarr/Sonarr renvoient les genres TMDB/TVDB en
 * anglais (« Science Fiction », « Drama »…) : on les affiche en français.
 * Un genre inconnu est laissé tel quel.
 */
const GENRES_FR: Record<string, string> = {
    action: "Action",
    "action & adventure": "Action & aventure",
    adventure: "Aventure",
    animation: "Animation",
    anime: "Anime",
    biography: "Biographie",
    children: "Enfants",
    comedy: "Comédie",
    crime: "Policier",
    documentary: "Documentaire",
    drama: "Drame",
    family: "Famille",
    fantasy: "Fantastique",
    "game show": "Jeu télévisé",
    history: "Histoire",
    horror: "Horreur",
    kids: "Enfants",
    "martial arts": "Arts martiaux",
    "mini-series": "Mini-série",
    music: "Musique",
    musical: "Comédie musicale",
    mystery: "Mystère",
    news: "Actualités",
    reality: "Téléréalité",
    romance: "Romance",
    "sci-fi & fantasy": "SF & fantastique",
    "science fiction": "Science-fiction",
    "science-fiction": "Science-fiction",
    soap: "Feuilleton",
    sport: "Sport",
    suspense: "Suspense",
    talk: "Talk-show",
    "talk show": "Talk-show",
    thriller: "Thriller",
    "tv movie": "Téléfilm",
    war: "Guerre",
    "war & politics": "Guerre & politique",
    western: "Western",
};

export function genreFr(name: string): string {
    return GENRES_FR[name.trim().toLowerCase()] ?? name;
}
