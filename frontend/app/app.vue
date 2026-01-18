<template>
  <div class="min-h-screen bg-gray-100 flex flex-col">
    <!-- Top Navigation -->
    <header class="bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
      <div class="flex items-center gap-4">
        <h1 class="text-2xl font-bold text-gray-900 tracking-tight">Lumen Digest</h1>
        <div v-if="totalArticles > 0" class="flex gap-2">
          <span class="px-2 py-1 bg-gray-100 text-gray-600 text-xs font-medium rounded">
            {{ totalArticles }} Total Articles
          </span>
          <span :class="['px-2 py-1 text-xs font-medium rounded', uncategorizedCount > 0 ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600']">
            {{ uncategorizedCount }} Uncategorized
          </span>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2">
          <label for="time-window" class="text-xs font-medium text-gray-500">Window</label>
          <select
            id="time-window"
            v-model="timeWindowDays"
            class="text-xs rounded-md border-gray-300 bg-white px-2 py-1 text-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          >
            <option :value="0">All time</option>
            <option :value="1">Last 24 hours</option>
            <option :value="3">Last 3 days</option>
            <option :value="7">Last 7 days</option>
            <option :value="30">Last 30 days</option>
          </select>
        </div>
        <!-- <button 
          @click="syncAndRefresh" 
          class="p-2 text-gray-400 hover:text-indigo-600 transition-colors"
          title="Refresh view"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
        </button> -->
        <button 
          @click="syncAndRefresh" 
          :disabled="loading"
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-all"
        >
          <span v-if="loading" class="animate-spin mr-2">🔄</span>
          {{ loading ? 'Processing...' : 'Refresh' }}
        </button>
      </div>
    </header>

    <div class="flex-1 flex overflow-hidden">
      <!-- Sidebar Navigation -->
      <aside class="w-64 bg-white border-r border-gray-200 overflow-y-auto hidden md:block">
        <nav class="p-4 space-y-2">
          <p class="text-[10px] font-bold text-gray-400 uppercase tracking-widest px-3 mb-2">Categories</p>

          <button 
            @click="activeCategory = 'all'"
            :class="['w-full flex justify-between items-center px-3 py-2 text-sm font-medium rounded-md transition-colors', activeCategory === 'all' ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-50']"
          >
            <span>All Articles</span>
            <span class="text-xs bg-gray-200 text-gray-800 px-2 rounded-full">{{ totalArticles }}</span>
          </button>

          <div v-for="node in categoryTreeWithCounts" :key="node.id" class="space-y-1">
            <button 
              @click="activeCategory = node.id"
              :class="[
                'w-full flex justify-between items-center px-3 py-2 text-sm font-semibold rounded-md transition-colors',
                activeCategory === node.id ? 'bg-indigo-50 text-indigo-700' : 'text-gray-700 hover:bg-gray-50'
              ]"
            >
              <span class="truncate pr-2">{{ node.label }}</span>
              <span class="text-[10px] bg-gray-100 text-gray-700 px-2 rounded-full">
                {{ node.count }}
              </span>
            </button>

            <button
              v-for="child in node.children"
              :key="child.id"
              @click="activeCategory = child.id"
              :class="[
                'w-full flex justify-between items-center pl-6 pr-3 py-2 text-sm font-medium rounded-md transition-colors',
                activeCategory === child.id ? 'bg-indigo-50 text-indigo-700' : 'text-gray-600 hover:bg-gray-50'
              ]"
            >
              <span class="truncate pr-2">{{ child.label }}</span>
              <span class="text-[10px] bg-gray-100 text-gray-700 px-2 rounded-full">
                {{ child.count }}
              </span>
            </button>
          </div>

          <button 
            @click="activeCategory = 'other'"
            :class="[
              'w-full flex justify-between items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
              activeCategory === 'other' ? 'bg-red-50 text-red-700' : 'text-gray-600 hover:bg-gray-50'
            ]"
          >
            <span class="truncate pr-2">Other / Uncategorized</span>
            <span class="text-xs px-2 rounded-full bg-red-100 text-red-700">
              {{ uncategorizedCount }}
            </span>
          </button>
        </nav>
      </aside>

      <!-- Main Content -->
      <main class="flex-1 overflow-y-auto bg-gray-50 p-6">

        <!-- Loading -->
        <div v-if="loading && articles.length === 0" class="flex flex-col items-center justify-center h-64 text-gray-500">
          <div class="animate-bounce text-4xl mb-4">🤖</div>
          <p class="italic text-lg">Lumen AI is reading and sorting your news...</p>
        </div>

        <!-- Feed -->
        <div v-else-if="filteredArticles.length > 0" class="max-w-3xl mx-auto space-y-6">
          <div v-for="article in filteredArticles" :key="article.id" class="bg-white shadow-sm rounded-xl border border-gray-200 overflow-hidden hover:border-indigo-300 transition-colors">
            <div class="p-6">
              <div class="flex justify-between items-start gap-4">
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-2">
                    <span :class="['text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-full border', (article.category_id || 'uncategorized') === 'uncategorized' ? 'bg-red-50 text-red-600 border-red-100' : 'bg-indigo-50 text-indigo-600 border-indigo-100']">
                      {{ categoryLabel(article.category_id) }}
                    </span>
                    <span class="text-gray-400 text-[10px] font-medium">
                      {{ new Date(article.published_at).toLocaleDateString() }}
                    </span>
                    <span v-if="articleSource(article)" class="text-gray-400 text-[10px] font-medium">
                      • {{ articleSource(article) }}
                    </span>
                  </div>
                  <a :href="article.url" target="_blank" class="text-lg font-bold text-gray-900 hover:text-indigo-600 leading-snug">
                    {{ stripHtml(article.title) }}
                  </a>
                </div>
              </div>

              <!-- OpenAI Summary -->
              <div class="mt-4 text-gray-700 text-sm leading-relaxed">
                <div v-html="formatSummary(article.summary)" class="prose prose-sm prose-indigo custom-summary"></div>
              </div>

              <div class="mt-4 pt-4 border-t border-gray-50 flex justify-end">
                <a :href="article.url" target="_blank" class="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center">
                  Full Article 
                  <svg class="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                </a>
              </div>
            </div>
          </div>
          <div class="flex items-center justify-between text-xs text-gray-500 border-t border-gray-100 pt-4">
            <div>
              Page {{ currentPage }} of {{ totalPages }}
              <span v-if="filteredTotal">• {{ filteredTotal }} results</span>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="prevPage"
                :disabled="currentPage <= 1"
                class="px-2 py-1 rounded border border-gray-200 text-gray-600 disabled:opacity-40"
              >
                Prev
              </button>
              <button
                v-for="pageNum in pageNumbers"
                :key="pageNum"
                @click="goToPage(pageNum)"
                :class="[
                  'px-2 py-1 rounded border text-gray-600',
                  pageNum === currentPage ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-gray-200'
                ]"
              >
                {{ pageNum }}
              </button>
              <button
                @click="nextPage"
                :disabled="currentPage >= totalPages"
                class="px-2 py-1 rounded border border-gray-200 text-gray-600 disabled:opacity-40"
              >
                Next
              </button>
              <label class="flex items-center gap-2 ml-2">
                <span class="text-gray-500">Page size</span>
                <select
                  v-model="pageSize"
                  class="text-xs rounded-md border-gray-300 bg-white px-2 py-1 text-gray-700"
                >
                  <option :value="10">10</option>
                  <option :value="20">20</option>
                  <option :value="50">50</option>
                  <option :value="100">100</option>
                </select>
              </label>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else class="text-center py-20 bg-white rounded-xl border-2 border-dashed border-gray-200 max-w-3xl mx-auto">
          <p class="text-gray-400">No articles found. Click "Sync" to fetch new content.</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
const config = useRuntimeConfig();
const articles = ref([]);
const allArticles = ref([]);
const filteredTotal = ref(0);
const currentPage = ref(1);
const pageSize = ref(20);
const loading = ref(false);
const activeCategory = ref('all');
const lang = ref('en');
const taxonomy = ref({ labels: {}, tree: [] });
const timeWindowDays = ref(3);

function selectedCategoryIds() {
  if (activeCategory.value === 'all') return null;
  if (activeCategory.value === 'other') return ['other', 'uncategorized'];
  return categoryDescendants.value[activeCategory.value] || [activeCategory.value];
}

// Load database content
async function fetchArticles() {
  try {
    const params = new URLSearchParams({
      days: String(timeWindowDays.value),
      page: String(currentPage.value),
      page_size: String(pageSize.value)
    });
    const ids = selectedCategoryIds();
    if (ids && ids.length) {
      ids.forEach((id) => params.append('category_ids', id));
    }
    const data = await $fetch(`${config.public.apiBase}/articles?${params.toString()}`);
    articles.value = data.items || [];
    filteredTotal.value = data.total ?? articles.value.length;
    const maxPages = Math.max(1, Math.ceil(filteredTotal.value / pageSize.value));
    if (currentPage.value > maxPages) {
      currentPage.value = maxPages;
      await fetchArticles();
    }
  } catch (err) {
    console.error('Error fetching articles:', err);
  }
}

async function fetchAllArticles() {
  try {
    const params = new URLSearchParams({ days: String(timeWindowDays.value), page: "1", page_size: "0" });
    const data = await $fetch(`${config.public.apiBase}/articles?${params.toString()}`);
    allArticles.value = data.items || [];
  } catch (err) {
    allArticles.value = [];
    console.error('Error fetching articles:', err);
  }
}

// Load taxonomy mapping + tree
async function loadTaxonomy() {
  try {
    taxonomy.value = await $fetch(`${config.public.apiBase}/digest/taxonomy?lang=${lang.value}`);
  } catch (err) {
    taxonomy.value = { labels: {}, tree: [] };
    console.warn('Failed to load taxonomy:', err);
  }
}

onMounted(async () => {
  // 1. Detect language
  try {
    const navLang = (navigator.language || 'en').toLowerCase();
    lang.value = navLang.startsWith('fr') ? 'fr' : 'en';
  } catch (_) {
    lang.value = 'en';
  }

  // 2. Initial load from local DB
  await syncAndRefresh();
});

// Sidebar stats logic
const categoryStats = computed(() => {
  const stats = {};
  allArticles.value.forEach(a => {
    const id = a.category_id || 'uncategorized';
    stats[id] = (stats[id] || 0) + 1;
  });
  return stats;
});

const uncategorizedCount = computed(() => {
  const stats = categoryStats.value;
  return (stats['other'] || 0) + (stats['uncategorized'] || 0);
});

const categoryTreeWithCounts = computed(() => {
  const stats = categoryStats.value;
  const buildNode = (node) => {
    const children = (node.children || []).map(buildNode);
    const descendants = [node.id, ...children.flatMap(child => child.descendants)];
    const count = descendants.reduce((sum, id) => sum + (stats[id] || 0), 0);
    return { ...node, children, descendants, count };
  };
  return (taxonomy.value.tree || []).map(buildNode);
});

const categoryDescendants = computed(() => {
  const map = {};
  const walk = (node) => {
    map[node.id] = node.descendants || [node.id];
    (node.children || []).forEach(walk);
  };
  categoryTreeWithCounts.value.forEach(walk);
  return map;
});

const filteredArticles = computed(() => {
  return articles.value;
});

function categoryLabel(categoryId) {
  if (!categoryId || categoryId === 'uncategorized') return 'Uncategorized';
  return taxonomy.value.labels?.[categoryId] || categoryId;
}

async function syncAndRefresh() {
  loading.value = true;
  try {
    // 1. Run the heavy RSS sync & AI classification
    // await $fetch(`${config.public.apiBase}/digest/sync?limit=50`);

    // 2. Refresh categories and local articles list
    await loadTaxonomy();
    currentPage.value = 1;
    await Promise.all([
      fetchAllArticles(),
      fetchArticles()
    ]);

    if (uncategorizedCount.value > 0) {
      activeCategory.value = 'other';
    }
  } catch (err) {
    alert("Sync failed: " + err.message);
  } finally {
    loading.value = false;
  }
}

watch(activeCategory, () => {
  currentPage.value = 1;
  fetchArticles();
});

watch(timeWindowDays, () => {
  syncAndRefresh();
});

const totalArticles = computed(() => allArticles.value.length);
const totalPages = computed(() => Math.max(1, Math.ceil(filteredTotal.value / pageSize.value)));
const pageNumbers = computed(() => {
  const total = totalPages.value;
  const current = currentPage.value;
  const windowSize = 2;
  const start = Math.max(1, current - windowSize);
  const end = Math.min(total, current + windowSize);
  const pages = [];
  for (let i = start; i <= end; i += 1) {
    pages.push(i);
  }
  return pages;
});

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

watch(pageSize, () => {
  currentPage.value = 1;
  fetchArticles();
});

function stripHtml(text) {
  if (!text) return "";
  return text.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
}

function formatSummary(text) {
  if (!text) return "";
  let formatted = stripHtml(text);
  if (formatted.includes('- ') || formatted.includes('* ')) {
    formatted = formatted.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>');
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

function articleSource(article) {
  if (!article) return "";
  return stripHtml(article.source || "") || sourceName(article.url);
}
</script>

<style>
.custom-summary ul {
  list-style-type: disc;
}
.custom-summary li::marker {
  color: #6366f1; /* indigo-500 */
}
</style>
