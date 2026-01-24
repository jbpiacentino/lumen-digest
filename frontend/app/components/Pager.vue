<template>
  <div class="flex items-center justify-between text-xs text-gray-500 border-t border-gray-100 pt-4">
    <div>
      Page {{ currentPage }} of {{ totalPages }}
      <span v-if="filteredTotal">• {{ filteredTotal }} results</span>
    </div>
    <div class="flex items-center gap-2">
      <button
        @click="$emit('prev')"
        :disabled="currentPage <= 1"
        class="px-2 py-1 rounded border border-gray-200 text-gray-600 disabled:opacity-40"
      >
        Prev
      </button>
      <button
        v-for="pageNum in pageNumbers"
        :key="pageNum"
        @click="$emit('go', pageNum)"
        :class="[
          'px-2 py-1 rounded border text-gray-600',
          pageNum === currentPage ? 'border-indigo-300 bg-indigo-50 text-primary' : 'border-gray-200'
        ]"
      >
        {{ pageNum }}
      </button>
      <button
        @click="$emit('next')"
        :disabled="currentPage >= totalPages"
        class="px-2 py-1 rounded border border-gray-200 text-gray-600 disabled:opacity-40"
      >
        Next
      </button>
      <label class="flex items-center gap-2 ml-2">
        <span class="text-gray-500">Page size</span>
        <select
          :value="pageSize"
          @change="$emit('page-size', Number($event.target.value))"
          class="text-xs rounded-md border-gray-300 bg-white px-2 py-1 text-gray-700"
        >
          <option :value="10">10</option>
          <option :value="20">20</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>
      </label>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  currentPage: { type: Number, required: true },
  totalPages: { type: Number, required: true },
  filteredTotal: { type: Number, required: true },
  pageSize: { type: Number, required: true }
});

const pageNumbers = computed(() => {
  const total = props.totalPages;
  const current = props.currentPage;
  const windowSize = 2;
  const start = Math.max(1, current - windowSize);
  const end = Math.min(total, current + windowSize);
  const pages = [];
  for (let i = start; i <= end; i += 1) {
    pages.push(i);
  }
  return pages;
});
</script>
