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
          <div class="relative w-72">
            <MagnifyingGlassIcon class="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              id="news-search"
              v-model="searchQuery"
              type="text"
              class="input input-sm input-bordered w-full pl-9 pr-8"
              placeholder="Search"
            />
            <button
              class="btn btn-circle btn-xs absolute right-2 top-1/2 -translate-y-1/2 transition-opacity"
              type="button"
              @click="searchQuery = ''"
              aria-label="Clear search"
              :class="searchQuery ? 'opacity-100' : 'opacity-0 pointer-events-none'"
            >
              <XMarkIcon class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <!-- <label for="time-window" class="text-xs font-medium text-gray-500">Window</label> -->
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
      <div
        class="hidden md:flex flex-shrink-0 relative"
        :style="{ width: `${sidebarWidth}px` }"
      >
        <aside class="w-full bg-white border-r border-gray-200 overflow-y-auto">
          <CategoryList
            :category-tree-with-counts="categoryTreeWithCounts"
            :active-category="activeCategory"
            :total-articles="totalArticles"
            :uncategorized-count="uncategorizedCount"
            @select="activeCategory = $event"
          />
        </aside>
        <div
          class="absolute right-0 top-0 h-full w-1 cursor-col-resize bg-transparent hover:bg-gray-200 transition-colors"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize category sidebar"
          @pointerdown="startSidebarResize"
        ></div>
      </div>

      <!-- Main Content -->
      <main class="flex-1 overflow-y-auto bg-gray-50 p-6">

        <!-- Loading -->
        <div v-if="loading && articles.length === 0" class="flex flex-col items-center justify-center h-64 text-gray-500">
          <div class="animate-bounce text-4xl mb-4">🤖</div>
          <p class="italic text-lg">Lumen AI is reading and sorting your news...</p>
        </div>

        <!-- Feed -->
        <div v-else-if="displayArticles.length > 0" class="max-w-3xl mx-auto space-y-6">
          <Pager
            :current-page="currentPage"
            :total-pages="totalPages"
            :filtered-total="displayTotal"
            :page-size="pageSize"
            @prev="prevPage"
            @next="nextPage"
            @go="goToPage"
            @page-size="setPageSize"
          />
          <ArticleList
            :articles="displayArticles"
            :category-label="categoryLabel"
            :compact="true"
            :date-format="dateFormatOptions"
          />
          <Pager
            :current-page="currentPage"
            :total-pages="totalPages"
            :filtered-total="displayTotal"
            :page-size="pageSize"
            @prev="prevPage"
            @next="nextPage"
            @go="goToPage"
            @page-size="setPageSize"
          />
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
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/vue/24/solid';
import { onMounted, ref } from 'vue';

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
const searchQuery = ref('');
const sidebarWidth = ref(256);
const sidebarMinWidth = 200;
const sidebarMaxWidth = 420;

const startSidebarResize = (event) => {
  if (event.button !== 0) return;
  const startX = event.clientX;
  const startWidth = sidebarWidth.value;

  const onMove = (moveEvent) => {
    const nextWidth = startWidth + (moveEvent.clientX - startX);
    sidebarWidth.value = Math.max(sidebarMinWidth, Math.min(sidebarMaxWidth, nextWidth));
  };

  const onUp = () => {
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', onUp);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    localStorage.setItem('lumen.sidebarWidth', String(sidebarWidth.value));
  };

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
  window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', onUp);
  event.preventDefault();
};

onMounted(() => {
  const stored = Number(localStorage.getItem('lumen.sidebarWidth'));
  if (!Number.isNaN(stored) && stored > 0) {
    sidebarWidth.value = Math.max(sidebarMinWidth, Math.min(sidebarMaxWidth, stored));
  }
});

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

const searchActive = computed(() => searchQuery.value.trim().length > 0);

const searchResults = computed(() => {
  if (!searchActive.value) return [];
  const query = searchQuery.value.trim().toLowerCase();
  const ids = selectedCategoryIds();
  return allArticles.value.filter((article) => {
    const categoryId = article.category_id || 'uncategorized';
    const matchesCategory = !ids || ids.includes(categoryId);
    if (!matchesCategory) return false;
    const haystack = [
      article.title || '',
      article.summary || '',
      article.source || ''
    ].join(' ').toLowerCase();
    return haystack.includes(query);
  });
});

const displayTotal = computed(() => (
  searchActive.value ? searchResults.value.length : filteredTotal.value
));

const displayArticles = computed(() => {
  if (!searchActive.value) return articles.value;
  const start = (currentPage.value - 1) * pageSize.value;
  return searchResults.value.slice(start, start + pageSize.value);
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

watch(searchQuery, () => {
  currentPage.value = 1;
});

watch(timeWindowDays, () => {
  syncAndRefresh();
});

const totalArticles = computed(() => allArticles.value.length);
const totalPages = computed(() => Math.max(1, Math.ceil(displayTotal.value / pageSize.value)));
const dateFormatOptions = { year: "numeric", month: "short", day: "numeric" };

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

function setPageSize(newSize) {
  if (newSize === pageSize.value) return;
  pageSize.value = newSize;
  currentPage.value = 1;
  fetchArticles();
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
