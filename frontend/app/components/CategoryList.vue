<template>
  <nav class="p-4 space-y-2">
    <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest px-3 mb-2">Categories</p>

    <button 
      @click="$emit('select', 'all')"
      :class="['w-full flex justify-between items-center px-3 py-2 text-sm font-medium rounded-md transition-colors', activeCategory === 'all' ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-50']"
    >
      <span>All Articles</span>
      <span class="text-xs bg-gray-200 text-gray-800 px-2 rounded-full">{{ totalArticles }}</span>
    </button>

    <div v-for="node in categoryTreeWithCounts" :key="node.id" class="space-y-1">
      <button 
        @click="$emit('select', node.id)"
        :class="[
          'w-full flex justify-between items-center px-3 py-2 text-xs font-semibold rounded-md transition-colors',
          activeCategory === node.id ? 'bg-indigo-50 text-indigo-700' : 'text-gray-700 hover:bg-gray-50'
        ]"
      >
        <span class="truncate pr-2">{{ node.label }}</span>
        <span class="text-[10px] bg-gray-100 text-gray-700 px-2 rounded-full">
          {{ node.count }}
        </span>
      </button>

      <button
        v-for="child in node.children"
        :key="child.id"
        @click="$emit('select', child.id)"
        :class="[
          'w-full flex justify-between items-center pl-6 pr-3 py-2 text-sm font-medium rounded-md transition-colors',
          activeCategory === child.id ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-50'
        ]"
      >
        <span class="truncate pr-2">{{ child.label }}</span>
        <span class="text-[10px] bg-gray-100 text-gray-700 px-2 rounded-full">
          {{ child.count }}
        </span>
      </button>
    </div>

    <button 
      @click="$emit('select', 'other')"
      :class="[
        'w-full flex justify-between items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
        activeCategory === 'other' ? 'bg-red-50 text-red-700' : 'text-gray-600 hover:bg-gray-50'
      ]"
    >
      <span class="truncate pr-2">Other / Uncategorized</span>
      <span class="text-xs px-2 rounded-full bg-red-100 text-red-700">
        {{ uncategorizedCount }}
      </span>
    </button>
  </nav>
</template>

<script setup>
defineProps({
  categoryTreeWithCounts: { type: Array, required: true },
  activeCategory: { type: String, required: true },
  totalArticles: { type: Number, required: true },
  uncategorizedCount: { type: Number, required: true }
});
</script>
