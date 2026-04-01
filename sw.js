// Nombre del cache para que la app cargue rápido
const CACHE_NAME = 'safequito-v1';

// Escuchar el evento 'push' (Cuando Render envía la alerta)
self.addEventListener('push', function(event) {
    if (event.data) {
        const data = event.data.json();
        
        const options = {
            body: data.body,
            icon: './icon-100.png', // Asegúrate que este archivo exista en tu GitHub
            badge: './icon-100.png',
            vibrate: [200, 100, 200, 100, 400], // Hace que el cel vibre fuerte
            data: {
                url: './index.html' // A donde ir si el vecino toca la notificación
            },
            actions: [
                { action: 'open', title: 'Ver Alerta 🚨' }
            ]
        };

        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});

// Escuchar cuando el vecino toca la notificación
self.addEventListener('notificationclick', function(event) {
    event.notification.close(); // Cierra el globito de la notificación

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            // Si la app ya está abierta, ponerle el foco
            for (let i = 0; i < clientList.length; i++) {
                let client = clientList[i];
                if (client.url === '/' && 'focus' in client) {
                    return client.focus();
                }
            }
            // Si está cerrada, abrirla
            if (clients.openWindow) {
                return clients.openWindow('./index.html');
            }
        })
    );
});
