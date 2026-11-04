/*
 * Service worker do data-collect (AGENTS.md §2.17, §12). Guarda SÓ arquivos estáticos do app
 * (JS, CSS, fontes e ícones com hash em /assets e os ícones fixos). NUNCA cacheia resposta da API,
 * token, /config.json nem dados da equipe: não há uso offline de dados.
 */
const VERSAO = "estaticos-v1";
const FIXOS = [
  "/logo.svg",
  "/icone.svg",
  "/icone-192.png",
  "/icone-512.png",
  "/manifest.webmanifest",
];

function ehEstatico(url) {
  return (
    url.origin === self.location.origin &&
    (url.pathname.startsWith("/assets/") || FIXOS.includes(url.pathname))
  );
}

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(VERSAO).then((cache) => cache.addAll(FIXOS)));
  self.skipWaiting();
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((chaves) =>
        Promise.all(chaves.filter((c) => c !== VERSAO).map((c) => caches.delete(c))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (evento) => {
  const { request } = evento;
  const url = new URL(request.url);
  // Só GET estático, e nunca um pedido com credencial: o resto vai direto para a rede.
  if (request.method !== "GET" || request.headers.has("Authorization") || !ehEstatico(url)) return;
  evento.respondWith(
    caches.match(request).then(
      (guardado) =>
        guardado ||
        fetch(request).then((resposta) => {
          if (resposta.ok) {
            const copia = resposta.clone();
            caches.open(VERSAO).then((cache) => cache.put(request, copia));
          }
          return resposta;
        }),
    ),
  );
});
