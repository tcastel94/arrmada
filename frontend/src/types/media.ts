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
    resolution?: string | number | null;
    video_codec?: string | null;
    video_dynamic_range?: string | null;
    audio_codec?: string | null;
    audio_channels?: number | null;
    studio?: string | null;
    network?: string | null;
    clearlogo_url?: string | null;
    size_bytes: number | null;
    poster_url: string | null;
    source_service: string;
    has_file?: boolean;
    monitored?: boolean;
    added_at?: string | null;
    synced_at?: string;
}
