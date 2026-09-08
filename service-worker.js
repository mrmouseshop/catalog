// Service Worker для Mr. Mouse — делает сайт по-настоящему надёжным офлайн
// ПОСЛЕ первого успешного захода (актуально для тех, кто добавил сайт на
// «Экран Домой»). Работает только для страницы, открытой как обычный сайт
// (https://...) — на скачанный локальный файл (offline.html) это никак не
// влияет, там Service Worker вообще не регистрируется браузером.
//
// Стратегия — "сеть в приоритете" (вы выбрали именно этот вариант):
// пока есть интернет, всегда отдаём самую свежую версию с сервера и тут же
// обновляем кэш; как только сети нет — отдаём то, что успело закэшироваться
// при последнем успешном заходе, вместо пустого экрана с ошибкой.
//
// 08.09.2026: раньше "сеть в приоритете" означало БЕЗ ограничения по
// времени — respondWith ждал fetch(req) сколько угодно. На слабой
// мобильной сети (плохой Wi-Fi/сотовая связь в магазине) это выглядело
// как "зависшая" кнопка/переход: человек нажимал "Открыть каталог" (или
// просто открывал сайт), а страница подолгу не отвечала, потому что
// Service Worker всё это время молча ждал сетевой ответ, вместо того
// чтобы сразу показать то, что уже есть в кэше. Теперь сеть и кэш
// "бегут наперегонки" с ограничением NETWORK_TIMEOUT_MS: если сеть не
// успела вовремя — тут же отдаём кэш, а сетевой ответ (когда всё же
// придёт) всё равно обновит кэш в фоне для следующего захода. Когда сеть
// быстрая (обычный случай) — поведение не меняется, отдаём именно её.
const NETWORK_TIMEOUT_MS = 3000;

const CACHE_VERSION = 'mrmouse-v7';
const APP_SHELL = [
  './',
  'index.html',
  'manager.html',
  'photos.js',
  'manifest.json',
  'manifest-manager.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => {
      // Кэшируем по одному — если какой-то один ресурс временно недоступен
      // (например, ещё не закоммитился photos.js), это не должно срывать
      // установку всего Service Worker целиком
      return Promise.all(
        APP_SHELL.map((url) =>
          cache.add(url).catch((err) => {
            console.warn('[SW] не удалось закэшировать', url, err);
          })
        )
      );
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  // Трогаем только свои GET-запросы — сторонние ресурсы (шрифты, Telegram
  // SDK, сама NocoDB) не кэшируем, у них своя логика и свои CORS-правила
  if (req.method !== 'GET') return;
  let url;
  try {
    url = new URL(req.url);
  } catch (e) {
    return;
  }
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    (async () => {
      // Сетевой запрос запускаем один раз и переиспользуем и в гонке с
      // таймаутом, и (если понадобится) как "последнюю надежду" ниже —
      // fetch() нельзя вызывать повторно для одного и того же объекта Request.
      const networkPromise = fetch(req)
        .then((networkResponse) => {
          // Сеть ответила — тут же обновляем кэш этой свежей версией,
          // чтобы следующий офлайн-заход (или следующий тайм-аут) получил
          // именно её
          const copy = networkResponse.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(req, copy));
          return networkResponse;
        })
        .catch(() => null);

      const timedOut = Symbol('timeout');
      const timeoutPromise = new Promise((resolve) => {
        setTimeout(() => resolve(timedOut), NETWORK_TIMEOUT_MS);
      });

      const first = await Promise.race([networkPromise, timeoutPromise]);
      if (first && first !== timedOut) return first; // сеть успела вовремя

      // Сеть не ответила за отведённое время (или недоступна совсем) —
      // не заставляем человека ждать дальше, отдаём то, что уже лежит в
      // кэше с прошлого раза; для самой страницы дополнительно
      // подстраховываемся index.html (у него могла быть другая query-строка)
      const cached = (await caches.match(req)) || (await caches.match('index.html'));
      if (cached) return cached;

      // В кэше тоже ничего нет (например, самый первый заход и он же
      // оказался медленным) — донадеемся на сеть до конца, это лучше,
      // чем сразу показать ошибку
      const late = await networkPromise;
      return late || Response.error();
    })()
  );
});
