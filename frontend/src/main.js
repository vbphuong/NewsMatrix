import { createApp } from 'vue';

import App from './App.vue';
import router from './router';
import './assets/main.css';
import { hydrateAuth } from './lib/auth';

hydrateAuth();

createApp(App).use(router).mount('#app');
