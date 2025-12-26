self.addEventListener('install', (e) => {
  console.log('Service Worker instalado');
});

self.addEventListener('fetch', (e) => {
  // Aquí se podría configurar el modo offline en el futuro
});