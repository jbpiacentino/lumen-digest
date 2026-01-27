<template>
  <div class="flex-1 flex overflow-hidden">
    <aside class="w-80 border-r border-gray-200 bg-white overflow-y-auto">
      <div class="p-4 border-b border-gray-200 space-y-3">
        <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Clusters</div>
        <div class="flex items-center gap-2">
          <label class="text-xs font-medium text-gray-500">Lang</label>
          <select
            v-model="clusterLang"
            class="text-xs rounded-md border-gray-300 bg-white px-2 py-1 text-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          >
            <option value="en">EN</option>
            <option value="fr">FR</option>
          </select>
          <button
            class="btn btn-xs btn-outline"
            type="button"
            :disabled="clusterRunning"
            @click="runClusters"
          >
            {{ clusterRunning ? 'Running…' : 'Run NMF' }}
          </button>
        </div>
        <button
          class="btn btn-xs btn-ghost w-full"
          type="button"
          :disabled="clusterLoading"
          @click="fetchClusters"
        >
          Refresh
        </button>
      </div>
      <div class="p-4 space-y-2">
        <button
          v-for="cluster in clusters"
          :key="cluster.id"
          class="w-full text-left rounded-lg border border-gray-200 p-3 hover:border-indigo-300 transition-colors"
          :class="selectedClusterId === cluster.id ? 'bg-indigo-50 border-indigo-300' : 'bg-white'"
          type="button"
          @click="selectCluster(cluster.id)"
        >
          <div class="flex items-center justify-between">
            <div class="text-xs font-semibold text-gray-800">
              {{ cluster.name || `Cluster #${cluster.id}` }}
            </div>
            <div class="text-[10px] text-gray-500">{{ cluster.member_count }}</div>
          </div>
          <div class="mt-2 text-[11px] text-gray-600 line-clamp-2">
            {{ (cluster.anchors || []).slice(0, 6).join(', ') }}
          </div>
        </button>
        <div v-if="!clusters.length" class="text-[11px] text-gray-400">
          No clusters yet.
        </div>
      </div>
    </aside>

    <main class="flex-1 overflow-y-auto bg-gray-50 p-6">
      <div v-if="!isAuthenticated" class="max-w-3xl mx-auto">
        <div class="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
          <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Access</div>
          <h2 class="mt-2 text-2xl font-bold text-gray-900">Sign in required</h2>
          <p class="mt-3 text-sm text-gray-600 leading-relaxed">
            Please log in to view clusters.
          </p>
        </div>
      </div>

      <div v-else class="space-y-6">
        <div v-if="selectedCluster" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div class="lg:col-span-1 space-y-4">
            <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
              <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Cluster</div>
              <div class="mt-3 space-y-2">
                <label class="text-[11px] font-semibold text-gray-600">Name</label>
                <div class="flex items-center gap-2">
                  <input
                    v-model="clusterNameDraft"
                    type="text"
                    class="input input-sm input-bordered w-full"
                    placeholder="Name this cluster"
                  />
                  <button
                    class="btn btn-xs btn-outline"
                    type="button"
                    :disabled="!clusterNameDirty"
                    @click="saveClusterName"
                  >
                    Save
                  </button>
                </div>
                <div class="text-xs text-gray-500">
                  {{ selectedCluster.member_count }} articles
                </div>
              </div>
            </div>

            <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3">
              <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Anchors</div>
              <div class="space-y-2">
                <div
                  v-for="anchor in anchorDrafts"
                  :key="anchor.id"
                  class="flex items-center gap-2"
                >
                  <input
                    v-model="anchor.phrase"
                    type="text"
                    class="input input-xs input-bordered w-full"
                  />
                  <button
                    class="btn btn-xs btn-outline"
                    type="button"
                    :disabled="!anchor.dirty"
                    @click="saveAnchor(anchor)"
                  >
                    Save
                  </button>
                  <button
                    class="btn btn-xs btn-ghost"
                    type="button"
                    @click="deleteAnchor(anchor)"
                  >
                    Remove
                  </button>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <input
                  v-model="newAnchorPhrase"
                  type="text"
                  class="input input-xs input-bordered w-full"
                  placeholder="Add anchor phrase"
                />
                <button
                  class="btn btn-xs btn-outline"
                  type="button"
                  :disabled="!newAnchorPhrase.trim()"
                  @click="addAnchor"
                >
                  Add
                </button>
              </div>
            </div>

            <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3">
              <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Assign</div>
              <div class="flex items-center gap-2">
                <select
                  v-model="clusterAssignCategory"
                  class="text-xs rounded-md border-gray-300 bg-white px-2 py-1 text-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                >
                  <option value="">Assign category…</option>
                  <option v-for="option in categoryOptions" :key="option.id" :value="option.id">
                    {{ option.label }}
                  </option>
                </select>
                <button
                  class="btn btn-xs btn-outline"
                  type="button"
                  :disabled="!clusterAssignCategory"
                  @click="assignCluster"
                >
                  Apply
                </button>
              </div>
            </div>
          </div>

          <div class="lg:col-span-2 space-y-4">
            <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
              <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Articles</div>
              <div class="mt-4">
                <ArticleList
                  :articles="clusterArticles"
                  :category-label="categoryLabel"
                  :category-options="categoryOptions"
                  :debug-data-by-id="debugDataById"
                  :anchor-keywords-by-id="anchorKeywordsById"
                  :compact="true"
                  :date-format="dateFormatOptions"
                  @update-review="updateArticleReview"
                  @reclassify="reclassifyArticle"
                  @load-debug="loadArticleDebug"
                  @create-anchor="createAnchor"
                  @reclassify-with-anchors="reclassifyArticleWithAnchors"
                  @extract-anchor-keywords="extractAnchorKeywords"
                />
              </div>
            </div>
          </div>
        </div>

        <div v-else class="rounded-xl border border-gray-200 bg-white p-8 text-center text-gray-500">
          Select a cluster to view its articles.
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';

const config = useRuntimeConfig();
const { authHeaders, isAuthenticated } = useAuth();
const apiFetch = useApiFetch();

const clusters = ref([]);
const clusterLang = ref('en');
const clusterRunning = ref(false);
const clusterLoading = ref(false);
const selectedClusterId = ref(null);
const selectedCluster = ref(null);
const clusterArticles = ref([]);
const clusterAssignCategory = ref('');
const clusterNameDraft = ref('');
const anchorDrafts = ref([]);
const newAnchorPhrase = ref('');
const debugDataById = ref({});
const anchorKeywordsById = ref({});

const taxonomy = ref({ labels: {}, tree: [] });
const dateFormatOptions = {
  year: 'numeric',
  month: 'short',
  day: 'numeric'
};

const categoryOptions = computed(() => {
  const options = [];
  const walk = (node, depth = 0) => {
    options.push({ id: node.id, label: node.label, depth });
    (node.children || []).forEach((child) => walk(child, depth + 1));
  };
  (taxonomy.value.tree || []).forEach((node) => walk(node, 0));
  const hasOther = options.some((option) => option.id === 'other');
  if (!hasOther) {
    options.push({ id: 'other', label: 'Other / Uncategorized', depth: 0 });
  }
  const hasUncategorized = options.some((option) => option.id === 'uncategorized');
  if (!hasUncategorized) {
    options.push({ id: 'uncategorized', label: 'Uncategorized', depth: 0 });
  }
  return options;
});

const clusterNameDirty = computed(() => {
  if (!selectedCluster.value) return false;
  return (clusterNameDraft.value || '') !== (selectedCluster.value.name || '');
});

function categoryLabel(categoryId) {
  if (!categoryId || categoryId === 'uncategorized') return 'Uncategorized';
  return taxonomy.value.labels?.[categoryId] || categoryId;
}

function updateArticleInState(updated) {
  if (!updated?.id) return;
  const idx = clusterArticles.value.findIndex((item) => item.id === updated.id);
  if (idx >= 0) {
    clusterArticles.value[idx] = { ...clusterArticles.value[idx], ...updated };
  }
}

async function loadTaxonomy() {
  try {
    taxonomy.value = await apiFetch(`${config.public.apiBase}/digest/taxonomy?lang=${clusterLang.value}`, {
      headers: authHeaders.value
    });
  } catch (_) {
    taxonomy.value = { labels: {}, tree: [] };
  }
}

async function updateArticleReview(payload) {
  try {
    const { articleId, ...body } = payload;
    const data = await apiFetch(`${config.public.apiBase}/articles/${articleId}/review`, {
      method: 'PATCH',
      body,
      headers: authHeaders.value
    });
    updateArticleInState(data);
  } catch (err) {
    console.error('Failed to update review:', err);
  }
}

async function loadArticleDebug(payload) {
  try {
    const { articleId, ...body } = payload;
    const data = await apiFetch(`${config.public.apiBase}/articles/${articleId}/reclassify`, {
      method: 'POST',
      body: { ...body, apply: false },
      headers: authHeaders.value
    });
    if (data?.debug) {
      debugDataById.value = {
        ...debugDataById.value,
        [articleId]: data.debug
      };
    }
  } catch (err) {
    console.error('Failed to load debug data:', err);
  }
}

async function reclassifyArticle(payload) {
  try {
    const { articleId, ...body } = payload;
    const data = await apiFetch(`${config.public.apiBase}/articles/${articleId}/reclassify`, {
      method: 'POST',
      body,
      headers: authHeaders.value
    });
    if (data?.article) {
      updateArticleInState(data.article);
    }
    if (data?.debug) {
      debugDataById.value = {
        ...debugDataById.value,
        [articleId]: data.debug
      };
    }
  } catch (err) {
    console.error('Failed to reclassify article:', err);
  }
}

async function reclassifyArticleWithAnchors(payload) {
  try {
    const { articleId } = payload;
    const data = await apiFetch(`${config.public.apiBase}/articles/${articleId}/reclassify`, {
      method: 'POST',
      body: { use_anchors: true, apply: true },
      headers: authHeaders.value
    });
    if (data?.article) {
      updateArticleInState(data.article);
    }
    if (data?.debug) {
      debugDataById.value = {
        ...debugDataById.value,
        [articleId]: data.debug
      };
    }
  } catch (err) {
    console.error('Failed to reclassify with anchors:', err);
  }
}

async function createAnchor(payload) {
  try {
    const { articleId, categoryId, language, text } = payload;
    await apiFetch(`${config.public.apiBase}/anchors`, {
      method: 'POST',
      body: { article_id: articleId, category_id: categoryId, language, text },
      headers: authHeaders.value
    });
  } catch (err) {
    console.error('Failed to create anchor:', err);
  }
}

async function extractAnchorKeywords(payload) {
  try {
    const { articleId, language } = payload;
    const data = await apiFetch(`${config.public.apiBase}/articles/${articleId}/anchor-keywords`, {
      method: 'GET',
      query: { lang: language, limit: 10 },
      headers: authHeaders.value
    });
    anchorKeywordsById.value = {
      ...anchorKeywordsById.value,
      [articleId]: data?.keywords || []
    };
  } catch (err) {
    console.error('Failed to extract anchor keywords:', err);
  }
}

async function fetchClusters() {
  try {
    clusterLoading.value = true;
    const data = await apiFetch(`${config.public.apiBase}/clusters`, {
      method: 'GET',
      query: { lang: clusterLang.value },
      headers: authHeaders.value
    });
    clusters.value = data?.items || [];
  } finally {
    clusterLoading.value = false;
  }
}

async function runClusters() {
  try {
    clusterRunning.value = true;
    await apiFetch(`${config.public.apiBase}/clusters/run`, {
      method: 'POST',
      query: { lang: clusterLang.value, n_components: 25, limit: 800 },
      headers: authHeaders.value
    });
    await fetchClusters();
  } finally {
    clusterRunning.value = false;
  }
}

async function selectCluster(id) {
  selectedClusterId.value = id;
  await Promise.all([loadCluster(), loadClusterArticles()]);
}

async function loadCluster() {
  if (!selectedClusterId.value) return;
  const data = await apiFetch(`${config.public.apiBase}/clusters/${selectedClusterId.value}`, {
    headers: authHeaders.value
  });
  selectedCluster.value = data;
  clusterNameDraft.value = data?.name || '';
  anchorDrafts.value = (data?.anchors || []).map((anchor) => ({
    ...anchor,
    original: anchor.phrase,
    dirty: false
  }));
}

async function loadClusterArticles() {
  if (!selectedClusterId.value) return;
  const data = await apiFetch(`${config.public.apiBase}/clusters/${selectedClusterId.value}/articles`, {
    query: { limit: 100, offset: 0 },
    headers: authHeaders.value
  });
  clusterArticles.value = data?.items || [];
}

async function saveClusterName() {
  if (!selectedClusterId.value) return;
  const data = await apiFetch(`${config.public.apiBase}/clusters/${selectedClusterId.value}`, {
    method: 'PATCH',
    body: { name: clusterNameDraft.value },
    headers: authHeaders.value
  });
  if (selectedCluster.value) {
    selectedCluster.value.name = data?.name || null;
  }
  await fetchClusters();
}

async function addAnchor() {
  if (!selectedClusterId.value || !newAnchorPhrase.value.trim()) return;
  const data = await apiFetch(`${config.public.apiBase}/clusters/${selectedClusterId.value}/anchors`, {
    method: 'POST',
    body: { phrase: newAnchorPhrase.value },
    headers: authHeaders.value
  });
  anchorDrafts.value.push({ ...data, original: data.phrase, dirty: false });
  newAnchorPhrase.value = '';
}

async function saveAnchor(anchor) {
  const data = await apiFetch(`${config.public.apiBase}/cluster-anchors/${anchor.id}`, {
    method: 'PATCH',
    body: { phrase: anchor.phrase },
    headers: authHeaders.value
  });
  anchor.original = data.phrase;
  anchor.dirty = false;
}

async function deleteAnchor(anchor) {
  await apiFetch(`${config.public.apiBase}/cluster-anchors/${anchor.id}`, {
    method: 'DELETE',
    headers: authHeaders.value
  });
  anchorDrafts.value = anchorDrafts.value.filter((item) => item.id !== anchor.id);
}

async function assignCluster() {
  if (!selectedClusterId.value || !clusterAssignCategory.value) return;
  await apiFetch(`${config.public.apiBase}/clusters/${selectedClusterId.value}/assign`, {
    method: 'POST',
    body: { category_id: clusterAssignCategory.value, apply: true },
    headers: authHeaders.value
  });
  await loadClusterArticles();
}

watch(anchorDrafts, (next) => {
  next.forEach((anchor) => {
    anchor.dirty = anchor.phrase !== anchor.original;
  });
}, { deep: true });

watch(clusterLang, async () => {
  await Promise.all([loadTaxonomy(), fetchClusters()]);
  selectedClusterId.value = null;
  selectedCluster.value = null;
  clusterArticles.value = [];
});

onMounted(async () => {
  if (!isAuthenticated.value) return;
  await Promise.all([loadTaxonomy(), fetchClusters()]);
});
</script>
