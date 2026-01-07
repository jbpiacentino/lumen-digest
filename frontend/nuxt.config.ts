// frontend/nuxt.config.ts

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  // Enable Nuxt 4 features
  future: {
    compatibilityVersion: 4,
  },
  
  modules: ['@nuxtjs/tailwindcss'],

  runtimeConfig: {
    public: {
      apiBase: process.env.API_BASE_URL || 'http://localhost:8000'
    }
  },

  // Nuxt 4 handles imports slightly differently, 
  // but for our logic, this remains standard.
  devtools: { enabled: true }
})
