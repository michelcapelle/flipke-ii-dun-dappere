import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withFetch } from '@angular/common/http';

import { routes } from './app.routes';
import { provideClientHydration } from '@angular/platform-browser';
import { initializeApp, provideFirebaseApp } from '@angular/fire/app';
import { getAuth, provideAuth } from '@angular/fire/auth';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }), 
    provideRouter(routes), 
    provideClientHydration(),
    provideHttpClient(withFetch()), provideFirebaseApp(() => initializeApp({"projectId":"flipke-635ba","appId":"1:330520963640:web:5ed2832797c8062816d4cd","storageBucket":"flipke-635ba.firebasestorage.app","apiKey":"AIzaSyBmlJICjME6Mi7dLmf4iWQZzr9BCzoyky4","authDomain":"flipke-635ba.firebaseapp.com","messagingSenderId":"330520963640","projectNumber":"330520963640","version":"2"})), provideAuth(() => getAuth())
  ]
};
