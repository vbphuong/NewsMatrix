<script setup>
import { computed, nextTick, onMounted, ref } from 'vue';

import { isAuthenticated } from '../lib/auth';
import { chatWithAssistant } from '../lib/backend-assistant';
import '../assets/ai-assistant-page.css';

const messages = ref([
  {
    role: 'assistant',
    content: 'Ask me anything about the documents already indexed in the chunk store. I will retrieve the most relevant chunks and answer from them.',
  },
]);
const prompt = ref('');
const loading = ref(false);
const error = ref('');
const queryVariations = ref([]);
const sources = ref([]);
const transcriptRef = ref(null);
const activeTab = ref('variations');

const canSend = computed(() => isAuthenticated.value && !loading.value && prompt.value.trim().length > 0);

async function scrollTranscriptToBottom() {
  await nextTick();
  const element = transcriptRef.value;
  if (element) {
    element.scrollTop = element.scrollHeight;
  }
}

async function sendMessage() {
  const message = prompt.value.trim();
  if (!message || loading.value || !isAuthenticated.value) {
    return;
  }

  messages.value.push({ role: 'user', content: message });
  prompt.value = '';
  loading.value = true;
  error.value = '';

  messages.value.push({ role: 'assistant', content: 'Thinking from the indexed chunks...' });
  await scrollTranscriptToBottom();

  try {
    const response = await chatWithAssistant(message);
    messages.value.pop();
    messages.value.push({ role: 'assistant', content: response.answer });
    queryVariations.value = response.query_variations ?? [];
    sources.value = response.sources ?? [];
  } catch (chatError) {
    messages.value.pop();
    error.value = chatError instanceof Error ? chatError.message : 'Failed to get assistant answer';
    messages.value.push({ role: 'assistant', content: 'I could not process that request.' });
  } finally {
    loading.value = false;
    await scrollTranscriptToBottom();
  }
}

function handleKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    void sendMessage();
  }
}

function clearConversation() {
  messages.value = [
    {
      role: 'assistant',
      content: 'Ask me anything about the documents already indexed in the chunk store. I will retrieve the most relevant chunks and answer from them.',
    },
  ];
  prompt.value = '';
  error.value = '';
  queryVariations.value = [];
  sources.value = [];
}

function useSuggestion(suggestion) {
  prompt.value = suggestion;
}

onMounted(() => {
  void scrollTranscriptToBottom();
});
</script>

<template>
  <section class="page ai-assistant-page">
    <div class="page__hero ai-assistant-hero">
      <span class="page__kicker">AI Assistant</span>
      <h1 class="page__title">Chunk chat.</h1>
      <p class="page__copy">
        Chat with the indexed document chunks. The backend uses the same retrieval and answer-generation pipeline from
        <strong>generate_answer.py</strong>.
      </p>
    </div>

    <div v-if="isAuthenticated" class="ai-assistant-grid">
      <article class="panel panel--soft assistant-panel">
        <div class="assistant-panel__head">
          <div>
            <h2 class="panel__title">Conversation</h2>
            <p class="panel__meta">Ask in natural language and the retriever will search the stored chunks.</p>
          </div>
          <button class="btn" type="button" @click="clearConversation">Clear</button>
        </div>

        <div ref="transcriptRef" class="assistant-chat__log">
          <template v-if="messages.length > 0">
            <article v-for="(message, index) in messages" :key="`${message.role}-${index}`" class="assistant-message"
              :class="message.role === 'user' ? 'assistant-message--user' : 'assistant-message--assistant'">
              <span class="assistant-message__role">{{ message.role === 'user' ? 'You' : 'Assistant' }}</span>
              <div class="assistant-message__text">{{ message.content }}</div>
            </article>
          </template>

          <div v-else class="assistant-empty">
            <strong>Start a conversation.</strong>
            <span>Try asking for a summary, a fact, or an image/table found in the chunks.</span>
          </div>
        </div>

        <form class="assistant-form" @submit.prevent="sendMessage">
          <label class="label">
            <span class="label__text">Your question</span>
            <textarea v-model="prompt" class="input assistant-form__input" rows="4"
              placeholder="Ask about a company, topic, statistic, or illustration in the chunks..."
              @keydown="handleKeydown" />
          </label>

          <div class="assistant-form__actions">
            <button class="btn btn--primary" type="submit" :disabled="loading || !canSend">
              {{ loading ? 'Thinking...' : 'Send' }}
            </button>
            <button class="btn" type="button"
              @click="useSuggestion('Give me a summary of the most relevant chunks.')">Summary</button>
            <button class="btn" type="button"
              @click="useSuggestion('Show me chunks that mention images, tables, or illustrations.')">Images /
              tables</button>
          </div>

          <p v-if="error" class="panel__notice notice--error">{{ error }}</p>
        </form>
      </article>

      <aside class="panel panel--soft assistant-context-panel">
        <div class="assistant-context-panel__head">
          <div>
            <h2 class="panel__title">Retriever context</h2>
            <p class="panel__meta">{{ sources.length }} returned chunks</p>
          </div>
        </div>

        <!-- Tab bar -->
        <div class="context-tabs">
          <button class="context-tab" :class="{ 'context-tab--active': activeTab === 'variations' }" type="button"
            @click="activeTab = 'variations'">
            Query variations
            <span class="context-tab__badge">{{ queryVariations.length }}</span>
          </button>
          <button class="context-tab" :class="{ 'context-tab--active': activeTab === 'chunks' }" type="button"
            @click="activeTab = 'chunks'">
            Top chunks
            <span class="context-tab__badge">{{ sources.length }}</span>
          </button>
        </div>

        <!-- Tab content -->
        <div class="assistant-context-list" v-if="activeTab === 'variations'">
          <template v-if="queryVariations.length > 0">
            <article v-for="(variant, index) in queryVariations" :key="`${variant}-${index}`" class="assistant-source">
              <p class="assistant-source__title">Variant {{ index + 1 }}</p>
              <p class="assistant-source__copy">{{ variant }}</p>
            </article>
          </template>
          <div v-else class="assistant-hint">No query variations yet.</div>
        </div>

        <div class="assistant-context-list" v-if="activeTab === 'chunks'">
          <template v-if="sources.length > 0">
            <article v-for="source in sources" :key="source.chunk_id" class="assistant-source">
              <p class="assistant-source__title">Chunk {{ source.chunk_id }}</p>
              <p class="assistant-source__meta">Score: {{ source.score.toFixed(4) }}</p>
              <p class="assistant-source__copy">{{ source.content }}</p>
            </article>
          </template>
          <div v-else class="assistant-hint">No chunks returned yet.</div>
        </div>

        <div v-if="sources.length === 0 && queryVariations.length === 0" class="assistant-hint">
          The right side will populate with the matched chunk ids, scores, and previews after you send a question.
        </div>
      </aside>
    </div>

    <div v-else class="panel panel--soft">
      You need to login to access this site.
    </div>
  </section>
</template>