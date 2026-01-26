<template>
  <div class="flex-1 flex overflow-hidden">
    <div
      v-if="isAuthenticated"
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

    <main class="flex-1 overflow-y-auto bg-gray-50 p-6">
      <ClientOnly>
        <div v-if="!isAuthenticated" class="max-w-3xl mx-auto">
          <div class="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
            <div class="text-xs font-semibold uppercase tracking-widest text-gray-400">Access</div>
            <h2 class="mt-2 text-2xl font-bold text-gray-900">Sign in required</h2>
            <p class="mt-3 text-sm text-gray-600 leading-relaxed">
              Please log in to view your news digest.
            </p>
          </div>
        </div>

        <div v-else class="w-full space-y-6">
          <div class="max-w-4xl mx-auto space-y-6">
            <div v-if="loading && articles.length === 0" class="flex flex-col items-center justify-center h-64 text-gray-500">
              <div class="animate-bounce text-4xl mb-4">🤖</div>
              <p class="italic text-lg">Lumen AI is reading and sorting your news...</p>
            </div>

            <div v-else class="space-y-6">
              <NewsFilters
                v-model:searchQuery="searchQuery"
                v-model:languageFilter="languageFilter"
                v-model:sourceFilter="sourceFilter"
                v-model:timeWindowDays="timeWindowDays"
                v-model:viewMode="viewMode"
                :language-options="languageOptions"
                :source-options="sourceOptions"
              />
              <div v-if="displayArticles.length === 0" class="text-center py-20 bg-white rounded-xl border-2 border-dashed border-gray-200">
                <p class="text-gray-400">No articles found. Click \"Refresh\" to fetch new content.</p>
              </div>
              <div v-else class="space-y-6">
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
                v-if="viewMode === 'cards'"
                :articles="displayArticles"
                :category-label="categoryLabel"
                :category-options="categoryOptions"
                :debug-data-by-id="debugDataById"
                :compact="true"
                :date-format="dateFormatOptions"
                @update-review="updateArticleReview"
                @reclassify="reclassifyArticle"
                @load-debug="loadArticleDebug"
                @delete-article="deleteArticle"
              />
              <div v-else class="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
                <div class="overflow-x-auto">
                  <table class="table table-zebra w-full">
                    <thead>
                      <tr class="text-xs uppercase tracking-widest text-gray-400">
                        <th class="w-48">
                          <button
                            class="inline-flex items-center gap-1"
                            type="button"
                            @click="toggleSort('category')"
                          >
                            Category
                            <span class="text-[10px]">{{ sortIndicator('category') }}</span>
                          </button>
                        </th>
                        <th class="w-48">
                          <button
                            class="inline-flex items-center gap-1"
                            type="button"
                            @click="toggleSort('source')"
                          >
                            Source
                            <span class="text-[10px]">{{ sortIndicator('source') }}</span>
                          </button>
                        </th>
                        <th>
                          <button
                            class="inline-flex items-center gap-1"
                            type="button"
                            @click="toggleSort('title')"
                          >
                            Title
                            <span class="text-[10px]">{{ sortIndicator('title') }}</span>
                          </button>
                        </th>
                        <th class="w-32">
                          <button
                            class="inline-flex items-center gap-1"
                            type="button"
                            @click="toggleSort('date')"
                          >
                            Date
                            <span class="text-[10px]">{{ sortIndicator('date') }}</span>
                          </button>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <template v-for="article in listArticles" :key="article.id">
                        <tr>
                          <td class="text-xs font-medium text-gray-600">{{ categoryLabel(article.category_id) }}</td>
                          <td class="text-sm text-gray-700">{{ getArticleSource(article) }}</td>
                          <td class="text-sm font-semibold text-gray-900">
                            <button
                              type="button"
                              class="text-left hover:text-indigo-600"
                              @click="toggleListExpand(article.id)"
                            >
                              {{ article.title }}
                            </button>
                          </td>
                          <td class="text-xs text-gray-500">{{ formatPublishedAt(article.published_at) }}</td>
                        </tr>
                        <tr v-if="expandedArticleId === article.id">
                          <td colspan="4" class="bg-gray-50">
                            <ArticleList
                              :articles="[article]"
                              :category-label="categoryLabel"
                              :category-options="categoryOptions"
                              :debug-data-by-id="debugDataById"
                              :compact="true"
                              :date-format="dateFormatOptions"
                              @update-review="updateArticleReview"
                              @reclassify="reclassifyArticle"
                              @load-debug="loadArticleDebug"
                              @delete-article="deleteArticle"
                            />
                          </td>
                        </tr>
                      </template>
                    </tbody>
                  </table>
                </div>
              </div>
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
            </div>
          </div>
        </div>
      </ClientOnly>
    </main>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const config = useRuntimeConfig();
const { authHeaders, isAuthenticated } = useAuth();

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
const timeWindowHours = ref(0);
const searchQuery = ref('');
const languageFilter = ref('');
const sourceFilter = ref('');
const viewMode = ref('cards');
const sortKey = ref('date');
const sortDir = ref('desc');
const sidebarWidth = ref(256);
const sidebarMinWidth = 200;
const sidebarMaxWidth = 420;
const debugDataById = ref({});
const storageKey = 'lumen.newsView';
const expandedArticleId = ref(null);

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

watch(isAuthenticated, (value) => {
  if (!value) {
    if (process.client) {
      try {
        localStorage.removeItem(storageKey);
      } catch (_) {
        // ignore storage errors
      }
    }
    navigateTo('/');
  }
});

onMounted(async () => {
  if (!isAuthenticated.value) return;
  if (process.client) {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const saved = JSON.parse(raw);
        if (typeof saved.searchQuery === 'string') searchQuery.value = saved.searchQuery;
        if (typeof saved.languageFilter === 'string') languageFilter.value = saved.languageFilter;
        if (typeof saved.sourceFilter === 'string') sourceFilter.value = saved.sourceFilter;
        if (typeof saved.timeWindowDays === 'number') timeWindowDays.value = saved.timeWindowDays;
        if (typeof saved.activeCategory === 'string') activeCategory.value = saved.activeCategory;
        if (typeof saved.currentPage === 'number' && saved.currentPage > 0) currentPage.value = saved.currentPage;
        if (saved.viewMode === 'cards' || saved.viewMode === 'list') viewMode.value = saved.viewMode;
      }
    } catch (_) {
      // ignore storage errors
    }
  }
  try {
    const navLang = (navigator.language || 'en').toLowerCase();
    lang.value = navLang.startsWith('fr') ? 'fr' : 'en';
  } catch (_) {
    lang.value = 'en';
  }
  await syncAndRefresh();
});

onMounted(() => {
  if (!process.client) return;
  const handler = () => {
    if (isAuthenticated.value) syncAndRefresh();
  };
  window.addEventListener('lumen:refresh', handler);
  onBeforeUnmount(() => window.removeEventListener('lumen:refresh', handler));
});

watch(timeWindowDays, () => {
  timeWindowHours.value = timeWindowDays.value === 1 ? 24 : 0;
}, { immediate: true });

function selectedCategoryIds() {
  if (activeCategory.value === 'all') return null;
  if (activeCategory.value === 'other') return ['other', 'uncategorized'];
  return categoryDescendants.value[activeCategory.value] || [activeCategory.value];
}

async function fetchArticles() {
  try {
    const params = new URLSearchParams({
      days: String(timeWindowHours.value ? 0 : timeWindowDays.value),
      hours: String(timeWindowHours.value),
      page: String(currentPage.value),
      page_size: String(pageSize.value)
    });
    const ids = selectedCategoryIds();
    if (ids && ids.length) {
      ids.forEach((id) => params.append('category_ids', id));
    }
    if (sourceFilter.value) {
      params.append('sources', sourceFilter.value);
    }
    const data = await $fetch(`${config.public.apiBase}/articles?${params.toString()}`, {
      headers: authHeaders.value
    });
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
    const params = new URLSearchParams({
      days: String(timeWindowHours.value ? 0 : timeWindowDays.value),
      hours: String(timeWindowHours.value),
      page: '1',
      page_size: '0'
    });
    if (sourceFilter.value) {
      params.append('sources', sourceFilter.value);
    }
    const data = await $fetch(`${config.public.apiBase}/articles?${params.toString()}`, {
      headers: authHeaders.value
    });
    allArticles.value = data.items || [];
  } catch (err) {
    allArticles.value = [];
    console.error('Error fetching articles:', err);
  }
}

async function loadTaxonomy() {
  try {
    taxonomy.value = await $fetch(`${config.public.apiBase}/digest/taxonomy?lang=${lang.value}`, {
      headers: authHeaders.value
    });
  } catch (err) {
    taxonomy.value = { labels: {}, tree: [] };
    console.warn('Failed to load taxonomy:', err);
  }
}

const categoryStats = computed(() => {
  const stats = {};
  allArticles.value.forEach((article) => {
    const id = article.category_id || 'uncategorized';
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
    const descendants = [node.id, ...children.flatMap((child) => child.descendants)];
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

const searchActive = computed(() => searchQuery.value.trim().length > 0);

const filteredAllArticles = computed(() => {
  const ids = selectedCategoryIds();
  return allArticles.value.filter((article) => {
    const categoryId = article.category_id || 'uncategorized';
    const matchesCategory = !ids || ids.includes(categoryId);
    if (!matchesCategory) return false;
    if (languageFilter.value && article.language !== languageFilter.value) return false;
    if (sourceFilter.value && getArticleSource(article) !== sourceFilter.value) return false;
    return true;
  });
});

const searchResults = computed(() => {
  if (!searchActive.value) return [];
  const query = searchQuery.value.trim().toLowerCase();
  return filteredAllArticles.value.filter((article) => {
    const haystack = [article.title || '', article.summary || '', article.source || '']
      .join(' ')
      .toLowerCase();
    return haystack.includes(query);
  });
});

const listBase = computed(() => (searchActive.value ? searchResults.value : filteredAllArticles.value));

const displayTotal = computed(() => {
  if (searchActive.value) return searchResults.value.length;
  if (viewMode.value === 'list') return listBase.value.length;
  return filteredTotal.value;
});

const displayArticles = computed(() => {
  if (!searchActive.value) {
    return articles.value.filter((article) => {
      if (languageFilter.value && article.language !== languageFilter.value) return false;
      if (sourceFilter.value && getArticleSource(article) !== sourceFilter.value) return false;
      return true;
    });
  }
  const start = (currentPage.value - 1) * pageSize.value;
  return searchResults.value.slice(start, start + pageSize.value);
});

const listArticles = computed(() => {
  if (viewMode.value !== 'list') return displayArticles.value;
  const sorted = [...listBase.value];
  const direction = sortDir.value === 'asc' ? 1 : -1;
  const collator = new Intl.Collator('en', { sensitivity: 'base', numeric: true });
  sorted.sort((a, b) => {
    if (sortKey.value === 'date') {
      const aTime = new Date(a.published_at || 0).getTime();
      const bTime = new Date(b.published_at || 0).getTime();
      return (aTime - bTime) * direction;
    }
    if (sortKey.value === 'source') {
      return collator.compare(getArticleSource(a), getArticleSource(b)) * direction;
    }
    if (sortKey.value === 'category') {
      return collator.compare(categoryLabel(a.category_id), categoryLabel(b.category_id)) * direction;
    }
    return collator.compare(a.title || '', b.title || '') * direction;
  });
  const start = (currentPage.value - 1) * pageSize.value;
  return sorted.slice(start, start + pageSize.value);
});

const languageOptions = computed(() => {
  const set = new Set();
  allArticles.value.forEach((article) => {
    if (article.language) set.add(article.language);
  });
  return Array.from(set).sort();
});

const sourceOptions = computed(() => {
  const set = new Set();
  allArticles.value.forEach((article) => {
    const source = getArticleSource(article);
    if (source) set.add(source);
  });
  return Array.from(set).sort();
});

function getArticleSource(article) {
  const name = (article.source || '').trim();
  if (name) return name;
  const url = article.url || '';
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch (_) {
    return '';
  }
}

function categoryLabel(categoryId) {
  if (!categoryId || categoryId === 'uncategorized') return 'Uncategorized';
  return taxonomy.value.labels?.[categoryId] || categoryId;
}

function updateArticleInState(updated) {
  if (!updated?.id) return;
  const updateList = (list) => {
    const idx = list.findIndex((item) => item.id === updated.id);
    if (idx >= 0) {
      list[idx] = { ...list[idx], ...updated };
    }
  };
  updateList(articles.value);
  updateList(allArticles.value);
}

function removeArticleFromState(articleId) {
  articles.value = articles.value.filter((item) => item.id !== articleId);
  allArticles.value = allArticles.value.filter((item) => item.id !== articleId);
  filteredTotal.value = Math.max(0, filteredTotal.value - 1);
}

async function updateArticleReview(payload) {
  try {
    const { articleId, ...body } = payload;
    const data = await $fetch(`${config.public.apiBase}/articles/${articleId}/review`, {
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
    const data = await $fetch(`${config.public.apiBase}/articles/${articleId}/reclassify`, {
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
    const data = await $fetch(`${config.public.apiBase}/articles/${articleId}/reclassify`, {
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

async function deleteArticle(payload) {
  try {
    const { articleId } = payload;
    await $fetch(`${config.public.apiBase}/articles/${articleId}`, {
      method: 'DELETE',
      headers: authHeaders.value
    });
    removeArticleFromState(articleId);
  } catch (err) {
    console.error('Failed to delete article:', err);
  }
}

async function syncAndRefresh() {
  if (!isAuthenticated.value) return;
  loading.value = true;
  try {
    await loadTaxonomy();
    currentPage.value = 1;
    await Promise.all([fetchAllArticles(), fetchArticles()]);

    if (uncategorizedCount.value > 0) {
      activeCategory.value = 'other';
    }
  } catch (err) {
    alert(`Sync failed: ${err?.message || err}`);
  } finally {
    loading.value = false;
  }
}

watch(activeCategory, () => {
  currentPage.value = 1;
  if (isAuthenticated.value) {
    fetchAllArticles();
    if (viewMode.value === 'cards') fetchArticles();
  }
});

watch(searchQuery, () => {
  currentPage.value = 1;
});

watch(
  [searchQuery, languageFilter, sourceFilter, timeWindowDays, activeCategory, currentPage, viewMode],
  () => {
    if (!process.client) return;
    const payload = {
      searchQuery: searchQuery.value,
      languageFilter: languageFilter.value,
      sourceFilter: sourceFilter.value,
      timeWindowDays: timeWindowDays.value,
      activeCategory: activeCategory.value,
      currentPage: currentPage.value,
      viewMode: viewMode.value,
    };
    try {
      localStorage.setItem(storageKey, JSON.stringify(payload));
    } catch (_) {
      // ignore storage errors
    }
  },
  { deep: false }
);

watch(languageFilter, () => {
  currentPage.value = 1;
  if (isAuthenticated.value) {
    fetchAllArticles();
    if (viewMode.value === 'cards') fetchArticles();
  }
});

watch(sourceFilter, () => {
  currentPage.value = 1;
  if (isAuthenticated.value) {
    fetchAllArticles();
    if (viewMode.value === 'cards') fetchArticles();
  }
});

watch(timeWindowDays, () => {
  if (isAuthenticated.value) syncAndRefresh();
});

const totalArticles = computed(() => allArticles.value.length);
const totalPages = computed(() => Math.max(1, Math.ceil(displayTotal.value / pageSize.value)));
const dateFormatOptions = { year: 'numeric', month: 'short', day: 'numeric' };
const dateFormatter = new Intl.DateTimeFormat('en-US', dateFormatOptions);

function formatPublishedAt(value) {
  if (!value) return '';
  try {
    return dateFormatter.format(new Date(value));
  } catch (_) {
    return '';
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value += 1;
    if (viewMode.value === 'cards') fetchArticles();
  }
}

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value -= 1;
    if (viewMode.value === 'cards') fetchArticles();
  }
}

function goToPage(pageNum) {
  if (pageNum >= 1 && pageNum <= totalPages.value && pageNum !== currentPage.value) {
    currentPage.value = pageNum;
    if (viewMode.value === 'cards') fetchArticles();
  }
}

function setPageSize(newSize) {
  if (newSize === pageSize.value) return;
  pageSize.value = newSize;
  currentPage.value = 1;
  if (viewMode.value === 'cards') fetchArticles();
}

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortKey.value = key;
    sortDir.value = key === 'date' ? 'desc' : 'asc';
  }
}

function sortIndicator(key) {
  if (sortKey.value !== key) return '';
  return sortDir.value === 'asc' ? '▲' : '▼';
}

function toggleListExpand(articleId) {
  expandedArticleId.value = expandedArticleId.value === articleId ? null : articleId;
}
</script>
