<template>
  <div :class="['bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden hover:border-indigo-300 transition-colors', compact ? 'p-4' : 'p-6']">
    <div>
      <div class="flex justify-between items-start gap-4">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-2">
            <span :class="['text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full border', (article.category_id || 'uncategorized') === 'uncategorized' ? 'bg-red-50 text-red-600 border-red-100' : 'bg-indigo-50 text-indigo-600 border-indigo-100']">
              {{ categoryLabel(displayCategoryId) }}
            </span>
            <span v-if="article.override_category_id" class="text-[10px] font-semibold uppercase tracking-wider text-amber-600">
              Override
            </span>
            <span class="text-gray-400 text-[10px] font-medium">
              {{ formattedDate }}
            </span>
            <span v-if="articleSource" class="text-gray-400 text-[10px] font-medium">
              • {{ articleSource }}
            </span>
            <label
              class="text-[10px] font-semibold uppercase tracking-wider text-indigo-600 cursor-pointer ml-1"
              :for="`review-toggle-${article.id}`"
            >
              Review
            </label>
          </div>
        </div>
      </div>

      <ArticleReviewPanel
        v-model:open="reviewOpen"
        :article="article"
        :category-label="categoryLabel"
        :category-options="categoryOptions"
        :debug-data="debugData"
        :compact="compact"
        :toggle-id="`review-toggle-${article.id}`"
        @update-review="emit('update-review', $event)"
        @reclassify="emit('reclassify', $event)"
        @load-debug="emit('load-debug', $event)"
        @refetch-full-text="emit('refetch-full-text', $event)"
      />

      <a :href="article.url" target="_blank" :class="[compact ? 'text-base' : 'text-lg', 'font-bold text-gray-900 hover:text-indigo-600 leading-snug']">
        {{ stripHtml(article.title) }}
      </a>

      <div :class="[compact ? 'mt-3' : 'mt-4', ' border-t border-gray-50 text-gray-700 text-sm leading-relaxed']">
        <div
          v-if="fullTextOpen"
          v-html="formatFullText(article.full_text, article.full_text_format)"
          class="prose prose-sm max-w-none"
        ></div>
        <div v-else class="prose prose-sm prose-indigo custom-summary">
          <span v-html="formatSummary(article.summary)"></span>
          <button
            v-if="article.full_text"
            class="inline-flex items-center text-indigo-600 hover:text-indigo-800 font-semibold text-xs ml-1"
            type="button"
            @click="fullTextOpen = true"
          >
            Read more
          </button>
        </div>
      </div>

      <div v-if="article.full_text && fullTextOpen" :class="[compact ? 'mt-3' : 'mt-4']">
        <button
          class="btn btn-xs btn-ghost"
          type="button"
          @click="fullTextOpen = !fullTextOpen"
        >
          Hide full text
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
  import { computed, ref, watch } from 'vue';
  import MarkdownIt from 'markdown-it';
  import ArticleReviewPanel from './ArticleReviewPanel.vue';
  
  const props = defineProps({
    article: { type: Object, required: true },
    categoryLabel: { type: Function, required: true },
    categoryOptions: { type: Array, default: () => [] },
    debugData: { type: Object, default: null },
    compact: { type: Boolean, default: false },
    dateFormat: { type: Object, default: null }
  });
  
  const emit = defineEmits(['update-review', 'reclassify', 'load-debug', 'refetch-full-text']);
  
  function stripHtml(text) {
    if (!text) return "";
    return text.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
  }
  
  function formatSummary(text) {
    if (!text) return "";
    let formatted = stripHtml(text);
    if (formatted.includes("- ") || formatted.includes("* ")) {
      formatted = formatted.replace(/^\s*[-*]\s+(.*)$/gm, "<li>$1</li>");
      return `<ul class="list-disc pl-5 space-y-1">${formatted}</ul>`;
    }
    return formatted;
  }

  const markdownRenderer = new MarkdownIt({
    html: false,
    linkify: true,
    typographer: true,
    breaks: false,
  });

  const defaultLinkOpen = markdownRenderer.renderer.rules.link_open || ((tokens, idx, options, env, self) => (
    self.renderToken(tokens, idx, options)
  ));

  markdownRenderer.renderer.rules.link_open = (tokens, idx, options, env, self) => {
    const token = tokens[idx];
    token.attrSet("target", "_blank");
    token.attrSet("rel", "noopener noreferrer");
    const classIndex = token.attrIndex("class");
    const existing = classIndex >= 0 ? token.attrs[classIndex][1] : "";
    const next = `${existing} text-indigo-600 underline decoration-1 underline-offset-2 hover:text-indigo-800`.trim();
    token.attrSet("class", next);
    return defaultLinkOpen(tokens, idx, options, env, self);
  };

  function formatFullText(text, format) {
    if (!text) return "";
    if (format === "markdown") {
      return markdownRenderer.render(text);
    }
    const sanitized = stripHtml(text);
    const blocks = sanitized.split(/\n{2,}/).map((block) => block.replace(/\n/g, "<br />"));
    return blocks.map((block) => `<p>${block}</p>`).join("");
  }
  
  function sourceName(url) {
    if (!url) return "";
    try {
      const host = new URL(url).hostname.replace(/^www\./, "");
      return host;
    } catch (_) {
      return "";
    }
  }
  
  const articleSource = computed(() => {
    const name = stripHtml(props.article.source || "");
    return name || sourceName(props.article.url);
  });
  
  const formattedDate = computed(() => {
    if (!props.article?.published_at) return "";
    const date = new Date(props.article.published_at);
    if (props.dateFormat) {
      try {
        return date.toLocaleDateString(undefined, props.dateFormat);
      } catch (_) {
        return date.toLocaleDateString();
      }
    }
    return date.toLocaleDateString();
  });
  
  const displayCategoryId = computed(() => (
  props.article.override_category_id || props.article.category_id
  ));
  
  const fullTextOpen = ref(false);
  const reviewOpen = ref(false);

  watch(
  () => props.article.id,
  () => {
    fullTextOpen.value = false;
  }
  );
</script>
