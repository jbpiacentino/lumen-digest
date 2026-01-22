<template>
  <main class="flex-1 bg-gray-50">
    <div class="max-w-3xl mx-auto px-6 py-16">
      <div class="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
        <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Welcome</div>
        <h1 class="mt-2 text-3xl font-bold text-gray-900">Lumen Digest</h1>
        <p class="mt-3 text-sm text-gray-600 leading-relaxed">
          Sign in to see your curated digest, review classifications, and keep
          the taxonomy clean. Create an account in seconds.
        </p>
        <div class="mt-6 flex flex-wrap items-center gap-3">
          <button
            class="btn btn-sm btn-neutral text-white"
            type="button"
            @click="openAuth('login')"
          >
            Log in
          </button>
          <button
            class="btn btn-sm btn-ghost"
            type="button"
            @click="openAuth('signup')"
          >
            Create account
          </button>
          <NuxtLink
            v-if="isAuthenticated"
            to="/news"
            class="btn btn-sm btn-outline"
          >
            Go to news
          </NuxtLink>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { watch } from 'vue';

const { openAuth, isAuthenticated } = useAuth();

watch(isAuthenticated, (value) => {
  if (value) navigateTo('/news');
});
</script>
