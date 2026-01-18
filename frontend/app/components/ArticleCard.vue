<template>
  <div :class="['bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden hover:border-indigo-300 transition-colors', compact ? 'p-4' : 'p-6']">
    <div>
      <div class="flex justify-between items-start gap-4">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-2">
            <span :class="['text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full border', (article.category_id || 'uncategorized') === 'uncategorized' ? 'bg-red-50 text-red-600 border-red-100' : 'bg-indigo-50 text-indigo-600 border-indigo-100']">
              {{ categoryLabel(article.category_id) }}
            </span>
            <span class="text-gray-400 text-[10px] font-medium">
              {{ formattedDate }}
            </span>
            <span v-if="articleSource" class="text-gray-400 text-[10px] font-medium">
              • {{ articleSource }}
            </span>
          </div>
          <a :href="article.url" target="_blank" :class="[compact ? 'text-base' : 'text-lg', 'font-bold text-gray-900 hover:text-indigo-600 leading-snug']">
            {{ stripHtml(article.title) }}
          </a>
        </div>
      </div>

      <div :class="[compact ? 'mt-3' : 'mt-4', 'text-gray-700 text-sm leading-relaxed']">
        <div v-html="formatSummary(article.summary)" class="prose prose-sm prose-indigo custom-summary"></div>
      </div>

      <div :class="[compact ? 'mt-3 pt-3' : 'mt-4 pt-4', 'border-t border-gray-50 flex justify-end']">
        <a :href="article.url" target="_blank" class="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center">
          Full Article 
          <svg class="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  article: { type: Object, required: true },
  categoryLabel: { type: Function, required: true },
  compact: { type: Boolean, default: false },
  dateFormat: { type: Object, default: null }
});

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
</script>
