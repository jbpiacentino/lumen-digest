<template>
  <div class="space-y-6">
    <ArticleCard
      v-for="article in articles"
      :key="article.id"
      :article="article"
      :category-label="categoryLabel"
      :compact="compact"
      :date-format="dateFormat"
    />
  </div>
</template>

<script setup>
defineProps({
  articles: { type: Array, required: true },
  categoryLabel: { type: Function, required: true },
  compact: { type: Boolean, default: false },
  dateFormat: { type: Object, default: null }
});
</script>
