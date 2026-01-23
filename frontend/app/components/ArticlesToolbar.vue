<template>
  <div class="w-full pb-4 border-b border-gray-200">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <button
        @click="$emit('refresh')"
        :disabled="loading"
        class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-all"
      >
        <span v-if="loading" class="animate-spin mr-2">🔄</span>
        {{ loading ? 'Processing...' : 'Refresh' }}
      </button>
    </div>


  </div>
</template>

<script setup>
defineProps({
  totalArticles: { type: Number, required: true },
  uncategorizedCount: { type: Number, required: true },
  loading: { type: Boolean, default: false },
  searchQuery: { type: String, default: '' },
  languageFilter: { type: String, default: '' },
  timeWindowDays: { type: Number, default: 0 },
  languageOptions: { type: Array, default: () => [] }
});

defineEmits(['refresh']);
</script>
