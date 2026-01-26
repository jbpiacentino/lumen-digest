<template>
  <div class="flex-1 flex overflow-hidden">
    <aside class="w-72 border-r border-gray-200 bg-white overflow-y-auto">
      <div class="p-4 border-b border-gray-200 space-y-3">
        <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Sources</div>
        <div class="relative w-full">
          <input
            v-model="sourceQuery"
            type="text"
            class="input input-sm input-bordered w-full"
            placeholder="Filter sources"
          />
        </div>
        <button class="btn btn-xs btn-outline w-full" type="button" @click="loadSources" :disabled="loadingSources">
          {{ loadingSources ? 'Loading…' : 'Refresh' }}
        </button>
      </div>
      <div class="p-4 space-y-2">
        <button
          v-for="source in filteredSources"
          :key="source"
          class="w-full text-left rounded-lg border border-gray-200 p-3 hover:border-indigo-300 transition-colors"
          :class="selectedSource === source ? 'bg-indigo-50 border-indigo-300' : 'bg-white'"
          type="button"
          @click="selectSource(source)"
        >
          <div class="text-xs font-semibold text-gray-800">{{ source }}</div>
        </button>
        <div v-if="!filteredSources.length" class="text-[11px] text-gray-400">
          No sources found.
        </div>
      </div>
    </aside>

    <main class="flex-1 overflow-y-auto bg-gray-50 p-6">
      <ClientOnly>
        <div v-if="!isAuthenticated" class="max-w-3xl mx-auto">
          <div class="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
            <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Access</div>
            <h2 class="mt-2 text-2xl font-bold text-gray-900">Sign in required</h2>
            <p class="mt-3 text-sm text-gray-600 leading-relaxed">
              Please log in to view sources.
            </p>
          </div>
        </div>

        <div v-else class="space-y-6">
          <div class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <div class="flex items-center justify-between gap-4">
              <div>
                <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Source</div>
                <div class="mt-1 text-sm font-semibold text-gray-800">
                  {{ selectedSource || 'Select a source' }}
                </div>
              </div>
              <div class="text-xs text-gray-500">
                {{ filteredTotal }} articles
              </div>
            </div>
          </div>

          <div v-if="selectedSource">
            <Pager
              :current-page="currentPage"
              :total-pages="totalPages"
              :filtered-total="filteredTotal"
              :page-size="pageSize"
              @prev="prevPage"
              @next="nextPage"
              @go="goToPage"
              @page-size="setPageSize"
            />
            <ArticleList
              :articles="articles"
              :category-label="categoryLabel"
              :category-options="categoryOptions"
              :debug-data-by-id="{}"
              :compact="true"
              :date-format="dateFormatOptions"
              @update-review="updateArticleReview"
              @reclassify="reclassifyArticle"
              @load-debug="loadArticleDebug"
              @delete-article="deleteArticle"
            />
            <Pager
              :current-page="currentPage"
              :total-pages="totalPages"
              :filtered-total="filteredTotal"
              :page-size="pageSize"
              @prev="prevPage"
              @next="nextPage"
              @go="goToPage"
              @page-size="setPageSize"
            />
          </div>
          <div v-else class="text-center py-16 text-gray-500">
            Select a source to view its articles.
          </div>
        </div>
      </ClientOnly>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';

const config = useRuntimeConfig();
const { authHeaders, isAuthenticated } = useAuth();

const sources = ref([]);
const sourceQuery = ref('');
const selectedSource = ref('');
const loadingSources = ref(false);

const articles = ref([]);
const filteredTotal = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);

const taxonomy = ref({ labels: {}, tree: [] });

const dateFormatOptions = { year: 'numeric', month: 'short', day: 'numeric' };

const filteredSources = computed(() => {
  const q = sourceQuery.value.trim().toLowerCase();
  if (!q) return sources.value;
  return sources.value.filter((source) => source.toLowerCase().includes(q));
});

const totalPages = computed(() => Math.max(1, Math.ceil(filteredTotal.value / pageSize.value)));

function categoryLabel(categoryId) {
  if (!categoryId || categoryId === 'uncategorized') return 'Uncategorized';
  return taxonomy.value.labels?.[categoryId] || categoryId;
}

const categoryOptions = computed(() => {
  const options = [];
  const walk = (node, depth = 0) => {
    options.push({ id: node.id, label: node.label, depth });
    (node.children || []).forEach((child) => walk(child, depth + 1));
  };
  (taxonomy.value.tree || []).forEach((node) => walk(node, 0));
  return options;
});

async function loadTaxonomy() {
  try {
    taxonomy.value = await $fetch(`${config.public.apiBase}/digest/taxonomy?lang=en`, {
      headers: authHeaders.value
    });
  } catch (_) {
    taxonomy.value = { labels: {}, tree: [] };
  }
}

async function loadSources() {
  if (!isAuthenticated.value) return;
  try {
    loadingSources.value = true;
    const params = new URLSearchParams({ page: '1', page_size: '0' });
    const data = await $fetch(`${config.public.apiBase}/articles?${params.toString()}`, {
      headers: authHeaders.value
    });
    const set = new Set();
    (data.items || []).forEach((article) => {
      const name = (article.source || '').trim();
      if (name) {
        set.add(name);
      } else if (article.url) {
        try {
          set.add(new URL(article.url).hostname.replace(/^www\./, ''));
        } catch (_) {
          // ignore
        }
      }
    });
    sources.value = Array.from(set).sort();
  } finally {
    loadingSources.value = false;
  }
}

async function fetchArticles() {
  if (!selectedSource.value) return;
  const params = new URLSearchParams({
    page: String(currentPage.value),
    page_size: String(pageSize.value)
  });
  params.append('sources', selectedSource.value);
  const data = await $fetch(`${config.public.apiBase}/articles?${params.toString()}`, {
    headers: authHeaders.value
  });
  articles.value = data.items || [];
  filteredTotal.value = data.total ?? articles.value.length;
}

function selectSource(source) {
  selectedSource.value = source;
  currentPage.value = 1;
  fetchArticles();
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value += 1;
    fetchArticles();
  }
}

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value -= 1;
    fetchArticles();
  }
}

function goToPage(pageNum) {
  if (pageNum >= 1 && pageNum <= totalPages.value && pageNum !== currentPage.value) {
    currentPage.value = pageNum;
    fetchArticles();
  }
}

function setPageSize(size) {
  pageSize.value = size;
  currentPage.value = 1;
  fetchArticles();
}

async function updateArticleReview(payload) {
  try {
    const { articleId, ...body } = payload;
    const data = await $fetch(`${config.public.apiBase}/articles/${articleId}/review`, {
      method: 'PATCH',
      body,
      headers: authHeaders.value
    });
    const idx = articles.value.findIndex((item) => item.id === data.id);
    if (idx >= 0) articles.value[idx] = data;
  } catch (err) {
    console.error('Failed to update review:', err);
  }
}

async function loadArticleDebug(payload) {
  try {
    const { articleId, ...body } = payload;
    await $fetch(`${config.public.apiBase}/articles/${articleId}/reclassify`, {
      method: 'POST',
      body: { ...body, apply: false },
      headers: authHeaders.value
    });
  } catch (err) {
    console.error('Failed to load debug data:', err);
  }
}

async function reclassifyArticle(payload) {
  try {
    const { articleId, ...body } = payload;
    const data = await $fetch(`${config.public.apiBase}/articles/${articleId}/reclassify`, {
      method: 'POST',
      body,
      headers: authHeaders.value
    });
    if (data?.article) {
      const idx = articles.value.findIndex((item) => item.id === data.article.id);
      if (idx >= 0) articles.value[idx] = data.article;
    }
  } catch (err) {
    console.error('Failed to reclassify article:', err);
  }
}

async function deleteArticle(payload) {
  try {
    const { articleId } = payload;
    await $fetch(`${config.public.apiBase}/articles/${articleId}`, {
      method: 'DELETE',
      headers: authHeaders.value
    });
    articles.value = articles.value.filter((item) => item.id !== articleId);
    filteredTotal.value = Math.max(0, filteredTotal.value - 1);
  } catch (err) {
    console.error('Failed to delete article:', err);
  }
}

onMounted(async () => {
  if (!isAuthenticated.value) return;
  await Promise.all([loadTaxonomy(), loadSources()]);
});
</script>
