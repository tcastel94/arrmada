import { MediaType } from ".";

/** A media item from the library */
export interface MediaItem {
    id: number;
    external_id: string;
    tmdb_id: number | null;
    title: string;
    type: MediaType;
    year: number | null;
    genres: string[] | null;
    quality: string | null;
    size_bytes: number | null;
    poster_url: string | null;
    source_service: string;
    added_at: string | null;
    synced_at: string;
}
