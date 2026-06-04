import { createRouter, createWebHistory } from 'vue-router';

import { authState, hydrateAuth } from './lib/auth';
import HomePage from './pages/HomePage.vue';
import LoginPage from './pages/LoginPage.vue';
import NewsPage from './pages/NewsPage.vue';
import NewsDetailPage from './pages/NewsDetailPage.vue';
import OrganizationPage from './pages/OrganizationPage.vue';
import OrganizationDetailPage from './pages/OrganizationDetailPage.vue';
import CategoryPage from './pages/CategoryPage.vue';
import WorkspacePage from './pages/WorkspacePage.vue';
import DocumentUploadPage from './pages/DocumentUploadPage.vue';
import PeoplePage from './pages/PeoplePage.vue';
import AiAssistantPage from './pages/AiAssistantPage.vue';
import AboutPage from './pages/AboutPage.vue';

const routes = [
  { path: '/', name: 'home', component: HomePage, meta: { public: true } },
  { path: '/login', name: 'login', component: LoginPage, meta: { authLayout: true } },
  { path: '/news', name: 'news', component: NewsPage, meta: { public: true } },
  { path: '/news/:newsId', name: 'news-detail', component: NewsDetailPage, meta: { public: true } },
  { path: '/about', name: 'about', component: AboutPage, meta: { public: true } },
  { path: '/organization', name: 'organization', component: OrganizationPage, meta: { public: true } },
  { path: '/organization/:organizationId', name: 'organization-detail', component: OrganizationDetailPage, meta: { public: true } },
  { path: '/category', name: 'category', component: CategoryPage, meta: { roles: ['Admin'] } },
  { path: '/documents', name: 'documents', component: DocumentUploadPage, meta: { roles: ['Admin'] } },
  { path: '/workspace', name: 'workspace', component: WorkspacePage, meta: { roles: ['Journalist', 'Admin'] } },
  { path: '/people', name: 'people', component: PeoplePage, meta: { roles: ['Admin'] } },
  { path: '/ai-assistant', name: 'ai-assistant', component: AiAssistantPage, meta: { requiresAuth: true } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

router.beforeEach((to) => {
  hydrateAuth();

  const token = authState.token;
  const role = authState.role;

  if (to.meta.requiresAuth && !token) {
    window.alert('You need to login to access this site.');
    return { path: '/login', query: { redirect: to.fullPath } };
  }

  if (Array.isArray(to.meta.roles) && !to.meta.roles.includes(role)) {
    if (to.path === '/workspace') {
      window.alert(role === 'User' ? 'Workspace is available only to Journalist and Admin roles.' : 'You need to login to access this site.');
    } else {
      window.alert('Only admin can access this page.');
    }

    return { path: token ? '/' : '/login' };
  }

  return true;
});

export default router;
