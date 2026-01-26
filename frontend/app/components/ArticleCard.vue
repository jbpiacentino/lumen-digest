<template>
  <div :class="['bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden hover:border-indigo-300 transition-colors', compact ? 'p-4' : 'p-6']">
    <div>
      <div class="flex justify-between items-start gap-4">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-2">
            <span :class="['text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full border', (article.category_id || 'uncategorized') === 'uncategorized' ? 'bg-red-50 text-red-600 border-red-100' : 'bg-indigo-50 text-primary border-indigo-100']">
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
              class="text-[10px] font-semibold uppercase tracking-wider text-primary cursor-pointer ml-1"
              :for="`review-toggle-${article.id}`"
            >
              <PencilSquareIcon class="inline-block w-4 h-4 mr-1" />
            </label>
            <button
              class="text-[10px] font-semibold uppercase tracking-wider text-red-600 hover:text-red-700 ml-auto"
              type="button"
              @click="openDeleteModal"
            >
              <TrashIcon class="inline-block w-4 h-4 mr-2" />
            </button>
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
      />

      <div class="flex items-center gap-2">
        <button
          type="button"
          :class="[compact ? 'text-base' : 'text-lg', 'font-bold text-gray-900 hover:text-primary leading-snug text-left']"
          @click="fullTextOpen = !fullTextOpen"
        >
          {{ stripHtml(article.title) }}
        </button>
        <a
          v-if="article.url"
          :href="article.url"
          target="_blank"
          rel="noopener noreferrer"
          class="btn btn-ghost text-primary btn-xs"
          aria-label="Open original article"
        >
          <ArrowTopRightOnSquareIcon class="w-4 h-4" />
        </a>
      </div>

      <div :class="[compact ? 'mt-3' : 'mt-4', ' border-t border-gray-50 text-gray-700 text-sm leading-relaxed']">
        <div
          v-if="fullTextOpen"
          v-html="formatFullText(article.full_text, article.full_text_format)"
          class="prose prose-sm max-w-none"
        ></div>
        <div v-else class="prose prose-sm prose-indigo custom-summary">
          <span v-html="renderSummaryWithSideImage(article.summary)"></span>
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

    <dialog ref="deleteDialog" class="modal">
      <div class="modal-box">
        <h3 class="font-semibold text-lg">Delete article?</h3>
        <p class="py-4 text-sm text-gray-600">
          This will permanently remove the article. This action cannot be undone.
        </p>
        <div class="modal-action">
          <button class="btn btn-outline btn-error" type="button" @click="confirmDelete">Delete</button>
          <button class="btn btn-primary" type="button" autofocus @click="closeDeleteModal">Cancel</button>
        </div>
      </div>
      <form method="dialog" class="modal-backdrop">
        <button aria-label="Close">close</button>
      </form>
    </dialog>
  </div>
</template>

<script setup>
  import { computed, ref, watch } from 'vue';
  import MarkdownIt from 'markdown-it';
  import ArticleReviewPanel from './ArticleReviewPanel.vue';
  import { ArrowTopRightOnSquareIcon, PencilSquareIcon, TrashIcon } from '@heroicons/vue/24/outline';
  
  const props = defineProps({
    article: { type: Object, required: true },
    categoryLabel: { type: Function, required: true },
    categoryOptions: { type: Array, default: () => [] },
    debugData: { type: Object, default: null },
    compact: { type: Boolean, default: false },
    dateFormat: { type: Object, default: null }
  });
  
  const emit = defineEmits(['update-review', 'reclassify', 'load-debug', 'delete-article']);
  
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
    const next = `${existing} text-primary underline decoration-1 underline-offset-2 hover:text-primary`.trim();
    token.attrSet("class", next);
    return defaultLinkOpen(tokens, idx, options, env, self);
  };

  function stripHtml(text) {
    if (!text) return "";
    return text.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
  }
  
  function formatSummary(text) {
    if (!text) return "";
    const trimmed = text.trim();
    if (/<[a-z][\s\S]*>/i.test(trimmed)) {
      return trimmed;
    }
    if (/[#*_`-]\s/.test(trimmed)) {
      return markdownRenderer.render(trimmed);
    }
    let formatted = stripHtml(trimmed);
    if (formatted.includes("- ") || formatted.includes("* ")) {
      formatted = formatted.replace(/^\s*[-*]\s+(.*)$/gm, "<li>$1</li>");
      return `<ul class="list-disc pl-5 space-y-1">${formatted}</ul>`;
    }
    return formatted;
  }

  function renderSummaryWithSideImage(text) {
    if (!text) return "";
    const html = formatSummary(text);
    const imgRegex = /<img[^>]*>/i;
    const match = html.match(imgRegex);
    if (!match) return html;
    const imageTag = match[0];
    const cleaned = html.replace(imgRegex, "");
    return `<div class="summary-with-image">${imageTag}<div class="summary-text">${cleaned}</div></div>`;
  }

  function formatFullText(text, format) {
    if (!text) return "";
    if (format === "markdown") {
      return markdownRenderer.render(text);
    }
    const sanitized = stripHtml(text);
    const blocks = sanitized.split(/\n{2,}/).map((block) => block.replace(/\n/g, "<br />"));
    return blocks.map((block) => `<p>${block}</p>`).join("");
  }

  const deleteDialog = ref(null);

  const openDeleteModal = () => {
    if (deleteDialog.value?.showModal) {
      deleteDialog.value.showModal();
    }
  };

  const closeDeleteModal = () => {
    if (deleteDialog.value?.close) {
      deleteDialog.value.close();
    }
  };

  const confirmDelete = () => {
    emit('delete-article', { articleId: props.article.id });
    closeDeleteModal();
  };
  
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

<style scoped>
:deep(.custom-summary img) {
  max-height: 120px !important;
  max-width: 180px !important;
  width: auto !important;
  height: auto !important;
  object-fit: contain;
}

:deep(.summary-with-image) {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

:deep(.summary-with-image img) {
  flex-shrink: 0;
  border-radius: 8px;
}

:deep(.summary-with-image .summary-text) {
  flex: 1 1 auto;
}
</style>
