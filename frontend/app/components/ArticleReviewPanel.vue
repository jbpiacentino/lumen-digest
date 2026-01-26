<template>
  <div :class="reviewOpen ? (compact ? 'mb-3 pt-3' : 'mb-4 pt-4') : ''">
    <div :class="['collapse collapse-arrow rounded-lg', reviewOpen ? 'border border-content' : 'border-transparent']">
      <input :id="toggleId" type="checkbox" v-model="reviewOpen" hidden=""/>
      <div class="collapse-title sr-only">Review</div>
      <div v-if="reviewOpen" class="collapse-content space-y-4">
        <div class="flex flex-wrap gap-4">
          <div :class="[labelWidthClass, 'text-sm font-semibold']">Current status</div>
          <div class="flex-1">
            <div v-if="showReason" class="text-[11px] text-gray-500">
              <span class="font-semibold text-gray-600">Why:</span>
              {{ reasonLabel }}
              <span v-if="confidenceText">• conf {{ confidenceText }}</span>
              <span v-if="runnerUpText">• runner-up {{ runnerUpText }}</span>
              <span v-if="marginText">• margin {{ marginText }}</span>
              <span v-if="article.language">• lang {{ article.language }}</span>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-4">
          <div :class="[labelWidthClass, 'text-sm font-semibold text-gray-600']">Category</div>
          <div class="flex-1 flex flex-wrap items-center gap-3">
            <div class="join">
              <label class="btn btn-xs btn-outline join-item" :class="reviewStatus === 'correct' ? 'btn-success border-neutral' : 'btn-ghost'">
                <input
                  class="hidden"
                  type="radio"
                  :name="`review-${article.id}`"
                  value="correct"
                  :checked="reviewStatus === 'correct'"
                  @change="setReviewStatus('correct')"
                />
                Correct
              </label>
              <label class="btn btn-xs btn-outline join-item" :class="reviewStatus === 'unreviewed' ? 'btn-info border-neutral' : 'btn-ghost'">
                <input
                  class="hidden"
                  type="radio"
                  :name="`review-${article.id}`"
                  value="unreviewed"
                  :checked="reviewStatus === 'unreviewed'"
                  @change="setReviewStatus('unreviewed')"
                />
                Unreviewed
              </label>
              <label class="btn btn-xs btn-outline join-item" :class="reviewStatus === 'incorrect' ? 'btn-error border-neutral' : 'btn-ghost'">
                <input
                  class="hidden"
                  type="radio"
                  :name="`review-${article.id}`"
                  value="incorrect"
                  :checked="reviewStatus === 'incorrect'"
                  @change="setReviewStatus('incorrect')"
                />
                Incorrect
              </label>
            </div>
            <div class="flex items-center gap-2 relative">
              <span class="text-[11px] text-gray-500">Override</span>
              <div class="relative">
                <input
                  v-model="overrideQuery"
                  type="text"
                  :class="['input input-xs input-bordered', inputWidthClass]"
                  placeholder="Type to search categories"
                  :disabled="reviewStatus !== 'incorrect'"
                  @focus="openOverrideMenu"
                  @keydown.enter.prevent="applyFirstOverride"
                  @blur="scheduleOverrideClose"
                />
                <div
                  v-if="showOverrideMenu && reviewStatus === 'incorrect'"
                  :class="['absolute z-20 mt-1 max-h-64 overflow-auto rounded-lg border border-gray-200 bg-white shadow-lg', menuWidthClass]"
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
          </div>
        </div>

        <div class="flex items-center gap-2">
          <input
            v-model="noteDraft"
            type="text"
            :class="['input input-xs input-bordered', inputWidthClass]"
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

        <div class="flex flex-wrap gap-4">
          <div :class="[labelWidthClass, 'text-sm font-semibold text-gray-600']">Review flags</div>
          <div class="flex-1 flex flex-wrap items-center gap-2">
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
        </div>

        <div class="flex flex-wrap gap-4">
          <div :class="[labelWidthClass, 'text-sm font-semibold text-gray-600']">Content</div>
          <div class="flex-1 flex flex-wrap items-center gap-2">
            <button
              class="btn btn-xs btn-outline"
              type="button"
              :disabled="anchorsPending"
              @click="extractAnchors"
            >
              {{ anchorsPending ? 'Extracting anchors…' : 'Extract anchors' }}
            </button>
          </div>
        </div>

        <div v-if="anchors.length" class="flex flex-wrap gap-4">
          <div :class="[labelWidthClass, 'text-sm font-semibold text-gray-600']">Anchors</div>
          <div class="flex-1">
            <div class="overflow-x-auto rounded-lg border border-gray-200 bg-white">
              <table class="table table-zebra w-full">
                <thead>
                  <tr class="text-[11px]  tracking-widest text-gray-400">
                    <th class="w-12">
                      <div class="flex items-center gap-1">
                        <span>Rank</span>
                        <div class="tooltip tooltip-bottom" data-tip="Order by BM25 score (1 is strongest).">
                          <InformationCircleIcon class="w-3.5 h-3.5 text-gray-400" />
                        </div>
                      </div>
                    </th>
                    <th>Phrase</th>
                    <th class="w-24 text-right">Score</th>
                    <th class="w-20 text-right">
                      <div class="flex items-center justify-end gap-1">
                        <span>Count</span>
                        <div class="tooltip tooltip-bottom" data-tip="How many times the phrase appears in the cleaned text.">
                          <InformationCircleIcon class="w-3.5 h-3.5 text-gray-400" />
                        </div>
                      </div>
                    </th>
                    <th class="w-24 text-right">
                      <div class="flex items-center justify-end gap-1">
                        <span>Presence</span>
                        <div class="tooltip tooltip-bottom" data-tip="Number of taxonomy categories/subcategories that already contain this anchor phrase.">
                          <InformationCircleIcon class="w-3.5 h-3.5 text-gray-400" />
                        </div>
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(anchor, index) in anchors" :key="anchor.phrase">
                    <td class="text-xs text-gray-400">{{ index + 1 }}</td>
                    <td class="text-xs font-medium text-gray-700">{{ anchor.phrase }}</td>
                    <td class="text-xs text-right text-gray-500">{{ formatScore(anchor.score) }}</td>
                    <td class="text-xs text-right text-gray-500">{{ anchor.count ?? 0 }}</td>
                    <td class="text-xs text-right text-gray-500">{{ anchor.presence_count ?? 0 }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-4">
          <div :class="[labelWidthClass, 'text-sm font-semibold text-gray-600']">Reclassify</div>
          <div class="flex-1 flex flex-wrap items-center gap-2">
            <label class="text-[11px] text-gray-500">Threshold</label>
            <input
              v-model.number="threshold"
              type="number"
              step="0.01"
              min="0"
              max="1"
              :class="['input input-xs input-bordered', numberWidthClass]"
            />
            <label class="text-[11px] text-gray-500">Margin</label>
            <input
              v-model.number="marginThreshold"
              type="number"
              step="0.01"
              min="0"
              max="1"
              :class="['input input-xs input-bordered', numberWidthClass]"
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
        </div>

        <div v-if="showTopK" class="text-xs text-gray-600">
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

        <div v-if="showInput" class="text-xs text-gray-600">
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
  import { computed, ref, watch, onBeforeUnmount } from 'vue';
  import { InformationCircleIcon } from '@heroicons/vue/24/outline';

  const props = defineProps({
    article: { type: Object, required: true },
    categoryLabel: { type: Function, required: true },
    categoryOptions: { type: Array, default: () => [] },
    debugData: { type: Object, default: null },
    compact: { type: Boolean, default: false },
    toggleId: { type: String, required: true },
    open: { type: Boolean, default: false },
  });

  const emit = defineEmits(['update-review', 'reclassify', 'load-debug', 'update:open']);
  const config = useRuntimeConfig();
  const { authHeaders } = useAuth();

  const reviewOpen = computed({
    get: () => props.open,
    set: (value) => emit('update:open', value),
  });

  const labelWidthClass = computed(() => (props.compact ? 'w-28' : 'w-40'));
  const inputWidthClass = computed(() => (props.compact ? 'w-44' : 'w-56'));
  const menuWidthClass = computed(() => (props.compact ? 'w-60' : 'w-72'));
  const numberWidthClass = computed(() => (props.compact ? 'w-14' : 'w-16'));

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

  const reviewStatus = computed(() => {
    const status = props.article.review_status;
    return status || "unreviewed";
  });

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
  const anchorsPending = ref(false);
  const anchors = ref([]);

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

  const setReviewStatus = (status) => {
    emit('update-review', { articleId: props.article.id, review_status: status });
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

  const extractAnchors = async () => {
    anchorsPending.value = true;
    try {
      const data = await $fetch(`${config.public.apiBase}/articles/${props.article.id}/extract-anchors`, {
        method: 'POST',
        headers: authHeaders.value,
      });
      anchors.value = data?.anchors || [];
    } catch (err) {
      console.error('Failed to extract anchors:', err);
      anchors.value = [];
    } finally {
      anchorsPending.value = false;
    }
  };

  onBeforeUnmount(() => {
    if (overrideCloseTimer) clearTimeout(overrideCloseTimer);
  });

  watch(
    () => props.article.id,
    () => {
      anchors.value = [];
    }
  );
</script>
