<template>
  <div class="min-h-screen bg-gray-100 flex flex-col">
    <header class="bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
      <div class="flex items-center gap-4">
        <NuxtLink to="/" class="text-2xl font-bold text-gray-900 tracking-tight">
          Lumen Digest
        </NuxtLink>
        <NuxtLink
          v-if="isAuthenticated"
          to="/news"
          class="text-xs font-semibold uppercase tracking-wider text-gray-500 hover:text-gray-700"
        >
          News
        </NuxtLink>
      </div>

      <div class="flex items-center gap-3">
        <div class="relative">
          <button
            class="inline-flex items-center px-3 py-2 border border-gray-200 text-xs font-semibold rounded-md shadow-sm bg-white text-gray-700 hover:bg-gray-50"
            type="button"
            @click="authOpen = !authOpen"
          >
            {{ authUser ? authUser.email : 'Sign in' }}
          </button>
          <div
            v-if="authOpen"
            class="absolute right-0 mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg z-20"
          >
            <div v-if="authUser" class="space-y-3">
              <div class="text-xs text-gray-500">Signed in as</div>
              <div class="text-sm font-semibold text-gray-800">{{ authUser.email }}</div>
              <button
                class="btn btn-xs btn-ghost"
                type="button"
                @click="logout"
              >
                Sign out
              </button>
            </div>
            <div v-else class="space-y-3">
              <div class="flex items-center gap-2">
                <button
                  class="btn btn-xs"
                  :class="authMode === 'login' ? 'btn-neutral text-white' : 'btn-ghost'"
                  type="button"
                  @click="authMode = 'login'"
                >
                  Login
                </button>
                <button
                  class="btn btn-xs"
                  :class="authMode === 'signup' ? 'btn-neutral text-white' : 'btn-ghost'"
                  type="button"
                  @click="authMode = 'signup'"
                >
                  Create account
                </button>
              </div>
              <div class="space-y-2">
                <input
                  v-model="authEmail"
                  type="email"
                  class="input input-sm input-bordered w-full"
                  placeholder="Email"
                />
                <input
                  v-model="authPassword"
                  type="password"
                  class="input input-sm input-bordered w-full"
                  placeholder="Password"
                />
              </div>
              <div v-if="authError" class="text-xs text-red-500">{{ authError }}</div>
              <button
                class="btn btn-xs btn-primary w-full"
                type="button"
                @click="authMode === 'signup' ? signup() : login()"
              >
                {{ authMode === 'signup' ? 'Create account' : 'Login' }}
              </button>
            </div>
          </div>
        </div>
        <button
          v-if="showRefresh"
          class="inline-flex items-center px-3 py-2 border border-transparent text-xs font-semibold rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700"
          type="button"
          @click="emitRefresh"
        >
          Refresh
        </button>
      </div>
    </header>

    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue';

const route = useRoute();
const {
  authUser,
  authOpen,
  authMode,
  authEmail,
  authPassword,
  authError,
  isAuthenticated,
  signup,
  login,
  logout
} = useAuth();

const showRefresh = computed(() => isAuthenticated.value && route.path === '/news');

const emitRefresh = () => {
  if (process.client) {
    window.dispatchEvent(new CustomEvent('lumen:refresh'));
  }
};
</script>
