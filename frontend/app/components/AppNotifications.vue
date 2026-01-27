<template>
  <div>
    <div v-if="authBanner" class="bg-amber-50 border-b border-amber-200 text-amber-900">
      <div class="mx-auto max-w-6xl px-6 py-3 flex items-center justify-between gap-4">
        <div class="text-sm font-semibold">
          {{ authBanner }}
        </div>
        <button class="btn btn-xs btn-ghost" type="button" @click="clearAuthBanner">
          Dismiss
        </button>
      </div>
    </div>

    <div class="fixed top-4 right-4 z-50 space-y-2 w-80">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="rounded-xl border shadow-sm px-4 py-3 text-sm flex items-start justify-between gap-3 bg-white"
        :class="toastClass(toast.type)"
      >
        <div class="flex-1 text-gray-700">{{ toast.message }}</div>
        <button class="btn btn-xs btn-ghost" type="button" @click="removeToast(toast.id)">✕</button>
      </div>
    </div>
  </div>
</template>

<script setup>
const { authBanner, toasts, clearAuthBanner, removeToast } = useNotifications();

const toastClass = (type) => {
  if (type === 'success') return 'border-emerald-200';
  if (type === 'info') return 'border-blue-200';
  return 'border-red-200';
};
</script>
