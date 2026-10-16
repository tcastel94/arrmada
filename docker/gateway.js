/**
 * ArrMada — passerelle HTTP du conteneur (le seul port exposé).
 * ----------------------------------------------------------------
 * Rôle identique à un `proxy_pass` nginx, en ~100 lignes de Node sans
 * aucune dépendance :
 *
 *     navigateur ──► :3420 (cette passerelle)
 *                      ├─ /api/*  ──► FastAPI   127.0.0.1:8420
 *                      └─ le reste ─► Next.js   127.0.0.1:3421
 *
 * Pourquoi pas les « rewrites » intégrés de Next.js ? Leur proxy :
 *   - coupe toute requête au bout de 30 s (flux temps réel SSE compris) ;
 *   - compresse les réponses, ce qui retarde les événements SSE ;
 *   - n'ajoute pas X-Forwarded-For : FastAPI verrait toutes les connexions
 *     venir de 127.0.0.1 et l'anti brute-force du login bloquerait TOUT le
 *     monde dès qu'un seul client se trompe 5 fois.
 *
 * Le Host d'origine est conservé et X-Forwarded-Proto/Host/For renseignés :
 * les redirections de FastAPI pointent donc vers la bonne adresse, y compris
 * derrière un reverse proxy HTTPS (Synology, Traefik, Nginx Proxy Manager…).
 */
"use strict";

const http = require("node:http");

const LISTEN_HOST = process.env.ARRMADA_HOST || "0.0.0.0";
const LISTEN_PORT = Number(process.env.ARRMADA_PORT || 3420);
const API = { host: "127.0.0.1", port: Number(process.env.ARRMADA_API_PORT || 8420) };
const WEB = { host: "127.0.0.1", port: Number(process.env.ARRMADA_WEB_PORT || 3421) };

// En-têtes « hop-by-hop » : propres à UNE connexion, jamais retransmis.
const HOP_BY_HOP = new Set([
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
]);

const agent = new http.Agent({ keepAlive: true, maxSockets: 256 });

function isApi(url) {
    return url === "/api" || url.startsWith("/api/") || url.startsWith("/api?");
}

function forwardHeaders(req) {
    const headers = {};
    for (const [name, value] of Object.entries(req.headers)) {
        if (!HOP_BY_HOP.has(name)) headers[name] = value;
    }
    const clientIp = req.socket.remoteAddress || "";
    // On AJOUTE l'IP du client à la chaîne existante (cas d'un reverse
    // proxy devant nous) ; uvicorn ne fait confiance qu'à 127.0.0.1.
    headers["x-forwarded-for"] = req.headers["x-forwarded-for"]
        ? `${req.headers["x-forwarded-for"]}, ${clientIp}`
        : clientIp;
    headers["x-forwarded-proto"] ??= req.socket.encrypted ? "https" : "http";
    headers["x-forwarded-host"] ??= req.headers.host || "";
    return headers;
}

const server = http.createServer((req, res) => {
    const target = isApi(req.url || "/") ? API : WEB;

    const upstream = http.request(
        {
            host: target.host,
            port: target.port,
            method: req.method,
            path: req.url,
            headers: forwardHeaders(req),
            agent,
        },
        (upRes) => {
            const headers = {};
            for (const [name, value] of Object.entries(upRes.headers)) {
                if (!HOP_BY_HOP.has(name)) headers[name] = value;
            }
            res.writeHead(upRes.statusCode || 502, upRes.statusMessage, headers);
            // Flux SSE : pas de mise en tampon, chaque événement part aussitôt.
            if (String(upRes.headers["content-type"] || "").startsWith("text/event-stream")) {
                res.flushHeaders();
                res.socket?.setNoDelay(true);
            }
            upRes.pipe(res);
            upRes.on("error", () => res.destroy());
        },
    );

    upstream.on("error", (err) => {
        if (res.headersSent) {
            res.destroy();
            return;
        }
        const which = target === API ? "API" : "interface";
        console.error(`[gateway] ${which} injoignable (${req.method} ${req.url}) : ${err.message}`);
        res.writeHead(502, { "content-type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ detail: `ArrMada ${which} unavailable (backend starting or stopped)` }));
    });

    // Navigateur parti avant la fin (onglet fermé, EventSource coupé) → on
    // libère l'amont. Après une réponse complète, on garde la connexion
    // keep-alive pour la requête suivante.
    res.on("close", () => {
        if (!res.writableFinished) upstream.destroy();
    });
    req.pipe(upstream);
});

// Pas de délai max sur les réponses longues (SSE, scans réseau, synchro
// TRaSH…). Les en-têtes doivent tout de même arriver en moins de 60 s.
server.requestTimeout = 0;
server.headersTimeout = 60_000;
server.keepAliveTimeout = 65_000;

server.listen(LISTEN_PORT, LISTEN_HOST, () => {
    console.log(
        `[gateway] ArrMada écoute sur http://${LISTEN_HOST}:${LISTEN_PORT} ` +
            `(API → :${API.port}, interface → :${WEB.port})`,
    );
});

for (const signal of ["SIGTERM", "SIGINT"]) {
    process.on(signal, () => {
        // Les flux SSE ne se terminent jamais d'eux-mêmes : on les coupe,
        // sinon `docker stop` attendrait 10 s avant de tuer le conteneur.
        server.close(() => process.exit(0));
        server.closeAllConnections();
    });
}
