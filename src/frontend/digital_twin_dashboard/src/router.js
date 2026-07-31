/**
 * router.js — Vue Router 4 Configuration
 * Digital Twin Dashboard routes
 */

import { createRouter, createWebHistory } from 'vue-router'

// Lazy-load route components for better initial load performance
const Dashboard = () => import('@/App.vue')

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: Dashboard,
    meta: { title: 'Digital Twin Dashboard' }
  },
  {
    path: '/devices',
    name: 'devices',
    component: () => import('@/components/DevicePanel.vue'),
    meta: { title: 'Device Management' }
  },
  {
    path: '/alerts',
    name: 'alerts',
    component: () => import('@/components/AlertList.vue'),
    meta: { title: 'Alert Center' }
  },
  {
    // Catch-all redirect to dashboard
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Update document title on navigation
router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} | Digital Twin` : 'Digital Twin Dashboard'
  next()
})

export default router
