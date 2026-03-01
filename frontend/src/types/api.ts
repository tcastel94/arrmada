/** API response wrapper */
export interface ApiResponse<T> {
    data: T;
    pagination?: PaginationMeta;
}

/** Pagination metadata */
export interface PaginationMeta {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
}

/** Error response */
export interface ApiError {
    detail: string;
    code?: string;
}

/** Health check response */
export interface HealthResponse {
    status: string;
    version: string;
}

/** Login request */
export interface LoginRequest {
    password: string;
}

/** Token response */
export interface TokenResponse {
    access_token: string;
    token_type: string;
    expires_in: number;
}
