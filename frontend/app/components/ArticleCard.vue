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
          </div>
          <a :href="article.url" target="_blank" :class="[compact ? 'text-base' : 'text-lg', 'font-bold text-gray-900 hover:text-indigo-600 leading-snug']">
            {{ stripHtml(article.title) }}
          </a>
        </div>
      </div>

      <div :class="[compact ? 'mt-3' : 'mt-4', 'text-gray-700 text-sm leading-relaxed']">
        <div v-html="formatSummary(article.summary)" class="prose prose-sm prose-indigo custom-summary"></div>
      </div>

      <div :class="[compact ? 'mt-3 pt-3' : 'mt-4 pt-4', 'border-t border-gray-50 flex items-center justify-between gap-4']">
        <div v-if="showReason" class="text-[11px] text-gray-500">
          <span class="font-semibold text-gray-600">Why:</span>
          {{ reasonLabel }}
          <span v-if="confidenceText">• conf {{ confidenceText }}</span>
          <span v-if="runnerUpText">• runner-up {{ runnerUpText }}</span>
          <span v-if="marginText">• margin {{ marginText }}</span>
          <span v-if="article.language">• lang {{ article.language }}</span>
        </div>
        <a :href="article.url" target="_blank" class="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center ml-auto">
          Full Article 
          <svg class="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002-2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
        </a>
      </div>

      <div :class="[compact ? 'mt-3 pt-3' : 'mt-4 pt-4', 'border-t border-gray-100']">
        <div class="flex flex-wrap items-center gap-2">
          <button
            class="btn btn-xs"
            :class="reviewStatus === 'correct' ? 'btn-success text-white' : 'btn-ghost'"
            type="button"
            @click="toggleReviewStatus('correct')"
          >
            Correct
          </button>
          <button
            class="btn btn-xs"
            :class="reviewStatus === 'incorrect' ? 'btn-error text-white' : 'btn-ghost'"
            type="button"
            @click="toggleReviewStatus('incorrect')"
          >
            Incorrect
          </button>

          <div class="flex items-center gap-2 relative">
            <span class="text-[11px] text-gray-500">Override</span>
            <div class="relative">
              <input
                v-model="overrideQuery"
                type="text"
                class="input input-xs input-bordered w-56"
                placeholder="Type to search categories"
                @focus="openOverrideMenu"
                @keydown.enter.prevent="applyFirstOverride"
                @blur="scheduleOverrideClose"
              />
              <div
                v-if="showOverrideMenu"
                class="absolute z-20 mt-1 max-h-64 w-72 overflow-auto rounded-lg border border-gray-200 bg-white shadow-lg"
              >
                <button
                  class="w-full text-left px-3 py-2 text-xs hover:bg-gray-100"
                  type="button"
                  @mousedown.prevent="selectOverride('')"
                >
                  None
                </button>
                <button
                  v-for="option in filteredCategoryOptions"
                  :key="option.id"
                  class="w-full text-left px-3 py-2 text-xs hover:bg-gray-100"
                  type="button"
                  @mousedown.prevent="selectOverride(option.id)"
                >
                  <span :style="{ paddingLeft: `${option.depth * 12}px` }">
                    {{ option.label }}
                  </span>
                </button>
                <div v-if="filteredCategoryOptions.length === 0" class="px-3 py-2 text-xs text-gray-400">
                  No matches
                </div>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-1">
            <span class="text-[11px] text-gray-500">Flags</span>
            <button
              v-for="flag in flagOptions"
              :key="flag.value"
              class="btn btn-xs"
              :class="activeFlags.has(flag.value) ? 'btn-warning text-white' : 'btn-ghost'"
              type="button"
              @click="toggleFlag(flag.value)"
            >
              {{ flag.label }}
            </button>
          </div>

          <div class="flex items-center gap-2">
            <button
              class="btn btn-xs"
              :class="showTopK ? 'btn-neutral text-white' : 'btn-ghost'"
              type="button"
              @click="toggleTopK"
            >
              Top-k
            </button>
            <button
              class="btn btn-xs"
              :class="showInput ? 'btn-neutral text-white' : 'btn-ghost'"
              type="button"
              @click="toggleInput"
            >
              Input text
            </button>
          </div>

          <div class="flex items-center gap-2">
            <label class="text-[11px] text-gray-500">Threshold</label>
            <input
              v-model.number="threshold"
              type="number"
              step="0.01"
              min="0"
              max="1"
              class="input input-xs input-bordered w-16"
            />
            <label class="text-[11px] text-gray-500">Margin</label>
            <input
              v-model.number="marginThreshold"
              type="number"
              step="0.01"
              min="0"
              max="1"
              class="input input-xs input-bordered w-16"
            />
            <button
              class="btn btn-xs btn-outline"
              type="button"
              :disabled="debugPending"
              @click="runReclassify"
            >
              {{ debugPending ? 'Running...' : 'Re-run classify' }}
            </button>
          </div>

          <div class="flex items-center gap-2">
            <input
              v-model="noteDraft"
              type="text"
              class="input input-xs input-bordered w-56"
              placeholder="Note / label for retraining"
            />
            <button
              class="btn btn-xs"
              :class="noteDirty ? 'btn-primary text-primary-content' : 'btn-ghost'"
              type="button"
              :disabled="!noteDirty"
              @click="saveNote"
            >
              Save note
            </button>
          </div>
        </div>

        <div v-if="showTopK" class="mt-3 text-xs text-gray-600">
          <div class="text-[11px] uppercase tracking-wider text-gray-400 font-semibold">Top-k scores</div>
          <div v-if="debugPending" class="mt-2 text-gray-400">Loading…</div>
          <ul v-else class="mt-2 space-y-1">
            <li v-for="entry in topK" :key="entry.category_id" class="flex items-center justify-between gap-3">
              <span class="truncate">
                {{ entry.label || categoryLabel(entry.category_id) }}
              </span>
              <span class="text-gray-400">{{ formatScore(entry.score) }}</span>
            </li>
            <li v-if="!topK.length" class="text-gray-400">No scores (text too short).</li>
          </ul>
        </div>

        <div v-if="showInput" class="mt-3 text-xs text-gray-600">
          <div class="text-[11px] uppercase tracking-wider text-gray-400 font-semibold">Input text</div>
          <div v-if="debugPending" class="mt-2 text-gray-400">Loading…</div>
          <div v-else class="mt-2 space-y-2">
            <div>
              <div class="text-[11px] font-semibold text-gray-500">Raw</div>
              <pre class="mt-1 whitespace-pre-wrap rounded-lg border border-gray-100 bg-gray-50 p-2 text-[11px] leading-relaxed text-gray-700">{{ rawText }}</pre>
            </div>
            <div>
              <div class="text-[11px] font-semibold text-gray-500">Cleaned</div>
              <pre class="mt-1 whitespace-pre-wrap rounded-lg border border-gray-100 bg-gray-50 p-2 text-[11px] leading-relaxed text-gray-700">{{ cleanedText }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  article: { type: Object, required: true },
  categoryLabel: { type: Function, required: true },
  categoryOptions: { type: Array, default: () => [] },
  debugData: { type: Object, default: null },
  compact: { type: Boolean, default: false },
  dateFormat: { type: Object, default: null }
});

const emit = defineEmits(['update-review', 'reclassify', 'load-debug']);

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

const showReason = computed(() => {
  return props.article.needs_review || (props.article.category_id || "uncategorized") === "other";
});

const reasonLabel = computed(() => {
  const reason = (props.article.reason || "").toLowerCase();
  if (reason === "no_text") return "short or missing text";
  if (reason === "low_confidence") return "low confidence";
  if (reason) return reason;
  return "unclassified";
});

const confidenceText = computed(() => {
  const value = props.article.confidence;
  if (value === null || value === undefined) return "";
  return Number(value).toFixed(3);
});

const runnerUpText = computed(() => {
  const value = props.article.runner_up_confidence;
  if (value === null || value === undefined) return "";
  return Number(value).toFixed(3);
});

const marginText = computed(() => {
  const value = props.article.margin;
  if (value === null || value === undefined) return "";
  return Number(value).toFixed(3);
});

const displayCategoryId = computed(() => (
  props.article.override_category_id || props.article.category_id
));

const reviewStatus = computed(() => props.article.review_status || null);

const noteDraft = ref(props.article.review_note || "");
const overrideQuery = ref("");
const showOverrideMenu = ref(false);
let overrideCloseTimer = null;

const currentOverrideLabel = computed(() => {
  const currentId = props.article.override_category_id;
  if (!currentId) return "";
  const match = props.categoryOptions.find((option) => option.id === currentId);
  return match?.label || currentId;
});

watch(
  () => props.article.override_category_id,
  () => {
    overrideQuery.value = currentOverrideLabel.value;
  },
  { immediate: true }
);

const filteredCategoryOptions = computed(() => {
  const query = overrideQuery.value.trim().toLowerCase();
  if (!query) return props.categoryOptions;
  return props.categoryOptions.filter((option) =>
    option.label.toLowerCase().includes(query) || option.id.toLowerCase().includes(query)
  );
});
watch(
  () => props.article.review_note,
  (next) => {
    noteDraft.value = next || "";
  }
);

const noteDirty = computed(() => (noteDraft.value || "") !== (props.article.review_note || ""));

const flagOptions = [
  { value: "low_confidence", label: "Low conf" },
  { value: "bad_taxonomy", label: "Bad taxonomy" },
  { value: "too_short", label: "Too short" },
];

const activeFlags = computed(() => {
  const flags = Array.isArray(props.article.review_flags) ? props.article.review_flags : [];
  return new Set(flags);
});

const showTopK = ref(false);
const showInput = ref(false);
const debugPending = ref(false);

const threshold = ref(0.36);
const marginThreshold = ref(0.07);

const topK = computed(() => props.debugData?.top_k || []);
const rawText = computed(() => props.debugData?.raw_text || "");
const cleanedText = computed(() => props.debugData?.cleaned_text || "");

watch(
  () => props.debugData,
  () => {
    debugPending.value = false;
  }
);

const toggleReviewStatus = (status) => {
  const next = reviewStatus.value === status ? null : status;
  emit('update-review', { articleId: props.article.id, review_status: next });
};

const updateOverride = (value) => {
  emit('update-review', {
    articleId: props.article.id,
    override_category_id: value || null,
  });
};

const openOverrideMenu = () => {
  showOverrideMenu.value = true;
  if (!overrideQuery.value) {
    overrideQuery.value = currentOverrideLabel.value;
  }
};

const scheduleOverrideClose = () => {
  if (overrideCloseTimer) clearTimeout(overrideCloseTimer);
  overrideCloseTimer = setTimeout(() => {
    showOverrideMenu.value = false;
  }, 120);
};

const selectOverride = (value) => {
  updateOverride(value);
  const next = props.categoryOptions.find((option) => option.id === value);
  overrideQuery.value = next ? next.label : "";
  showOverrideMenu.value = false;
};

const applyFirstOverride = () => {
  const first = filteredCategoryOptions.value[0];
  if (first) {
    selectOverride(first.id);
  }
};

const toggleFlag = (flag) => {
  const next = new Set(activeFlags.value);
  if (next.has(flag)) {
    next.delete(flag);
  } else {
    next.add(flag);
  }
  emit('update-review', { articleId: props.article.id, review_flags: Array.from(next) });
};

const requestDebug = (apply) => {
  debugPending.value = true;
  emit('load-debug', {
    articleId: props.article.id,
    threshold: threshold.value,
    margin_threshold: marginThreshold.value,
    min_len: 30,
    low_bucket: "other",
    top_k: 5,
    apply,
  });
};

const toggleTopK = () => {
  showTopK.value = !showTopK.value;
  if (showTopK.value && !props.debugData) {
    requestDebug(false);
  }
};

const toggleInput = () => {
  showInput.value = !showInput.value;
  if (showInput.value && !props.debugData) {
    requestDebug(false);
  }
};

const runReclassify = () => {
  debugPending.value = true;
  emit('reclassify', {
    articleId: props.article.id,
    threshold: threshold.value,
    margin_threshold: marginThreshold.value,
    min_len: 30,
    low_bucket: "other",
    top_k: 5,
    apply: true,
  });
};

const saveNote = () => {
  emit('update-review', { articleId: props.article.id, review_note: noteDraft.value });
};

const formatScore = (value) => {
  if (value === null || value === undefined) return "";
  return Number(value).toFixed(3);
};
</script>
