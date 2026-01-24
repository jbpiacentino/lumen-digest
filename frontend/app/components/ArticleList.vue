<template>
  <div class="space-y-6">
    <ArticleCard
      v-for="article in articles"
      :key="article.id"
      :article="article"
      :category-label="categoryLabel"
      :category-options="categoryOptions"
      :debug-data="debugDataById?.[article.id]"
      :compact="compact"
      :date-format="dateFormat"
      @update-review="emit('update-review', $event)"
      @reclassify="emit('reclassify', $event)"
      @load-debug="emit('load-debug', $event)"
      @refetch-full-text="emit('refetch-full-text', $event)"
      @delete-article="emit('delete-article', $event)"
    />
  </div>
</template>

<script setup>
const props = defineProps({
  articles: { type: Array, required: true },
  categoryLabel: { type: Function, required: true },
  categoryOptions: { type: Array, default: () => [] },
  debugDataById: { type: Object, default: () => ({}) },
  compact: { type: Boolean, default: false },
  dateFormat: { type: Object, default: null }
});

const emit = defineEmits(['update-review', 'reclassify', 'load-debug', 'refetch-full-text', 'delete-article']);
</script>
