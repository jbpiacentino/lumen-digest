<template>
  <nav class="p-4 space-y-2">
    <div class="flex items-center justify-between px-1">
      <p class="text-xs font-semibold uppercase tracking-widest text-base-content/60">Categories</p>
      <button
        class="btn btn-xs btn-outline"
        @click="collapseAll"
        type="button"
      >
          Collapse all
      </button>
    </div>

    <button 
      @click="$emit('select', 'all')"
      :class="[
        'btn btn-sm w-full justify-between',
        activeCategory === 'all' ? 'btn-primary text-primary-content' : 'btn-ghost'
      ]"
      type="button"
    >
      <span>All Articles</span>
      <span class="badge badge-sm">{{ totalArticles }}</span>
    </button>

    <div v-for="node in categoryTreeWithCounts" :key="node.id" class="space-y-1">
      <div class="flex items-center gap-2">
        <button
          class="btn btn-xs btn-square btn-ghost text-primary "
          @click.stop="toggleNode(node.id)"
          type="button"
          :aria-label="isExpanded(node.id) ? 'Collapse category' : 'Expand category'"
        >
          <MinusIcon v-if="isExpanded(node.id)" class="w-4 h-4"/>
          <PlusCircleIcon v-else class="w-4 h-4"/>
          
        </button>
        <button 
          @click="$emit('select', node.id)"
          :class="[
            'btn btn-sm w-full justify-between font-normal text-primary pl-1',
            activeCategory === node.id ? 'btn-primary text-primary-content' : 'btn-ghost'
          ]"
          type="button"
        >
          <span class="truncate pr-2">{{ node.label }}</span>
          <span class="badge badge-sm">{{ node.count }}</span>
        </button>
      </div>

      <button
        v-for="child in (isExpanded(node.id) ? node.children : [])"
        :key="child.id"
        @click="$emit('select', child.id)"
        :class="[
          'btn btn-sm w-full justify-between pl-10',
          activeCategory === child.id ? 'btn-primary text-primary-content' : 'btn-ghost'
        ]"
        type="button"
      >
        <span class="truncate pr-2 font-normal">{{ child.label }}</span>
        <span class="badge badge-sm">{{ child.count }}</span>
      </button>
    </div>

    <button 
      @click="$emit('select', 'other')"
      :class="[
        'btn btn-sm w-full justify-between',
        activeCategory === 'other' ? 'btn-error text-error-content' : 'btn-ghost text-error'
      ]"
      type="button"
    >
      <span class="truncate pr-2">Other / Uncategorized</span>
      <span class="badge badge-sm">{{ uncategorizedCount }}</span>
    </button>
  </nav>
</template>

<script setup>
import { ref, watch } from 'vue';
import { MinusIcon, PlusCircleIcon } from '@heroicons/vue/24/outline';

const props = defineProps({
  categoryTreeWithCounts: { type: Array, required: true },
  activeCategory: { type: String, required: true },
  totalArticles: { type: Number, required: true },
  uncategorizedCount: { type: Number, required: true }
});

const expandedIds = ref(new Set());

const initExpanded = (nodes) => {
  if (!nodes || !nodes.length) {
    expandedIds.value = new Set();
    return;
  }
  const next = new Set(expandedIds.value);
  if (next.size === 0) {
    nodes.forEach((node) => next.add(node.id));
  } else {
    nodes.forEach((node) => next.add(node.id));
  }
  expandedIds.value = next;
};

watch(
  () => props.categoryTreeWithCounts,
  (nodes) => initExpanded(nodes),
  { immediate: true }
);

const isExpanded = (id) => expandedIds.value.has(id);

const toggleNode = (id) => {
  const next = new Set(expandedIds.value);
  if (next.has(id)) {
    next.delete(id);
  } else {
    next.add(id);
  }
  expandedIds.value = next;
};

const collapseAll = () => {
  expandedIds.value = new Set();
};
</script>
