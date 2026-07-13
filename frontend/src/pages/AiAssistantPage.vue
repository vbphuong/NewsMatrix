<script setup>
import { computed, nextTick, onMounted, ref } from 'vue';

import { isAuthenticated } from '../lib/auth';
import { chatWithAssistant } from '../lib/backend-assistant';
import '../assets/ai-assistant-page.css';

const defaultMessages = () => [
  {
    role: 'assistant',
    content: 'Ask me anything about the documents already indexed in the chunk store. I will retrieve the most relevant chunks and answer from them.',
  },
];

const messages = ref(defaultMessages());
const prompt = ref('');
const loading = ref(false);
const error = ref('');
const queryVariations = ref([]);
const sources = ref([]);
const transcriptRef = ref(null);
const activeTab = ref('variations');
const selectedImage = ref(null);
const imagePreview = ref(null);
const imageInputRef = ref(null);

const canSend = computed(() => (
  isAuthenticated.value
  && !loading.value
  && (prompt.value.trim().length > 0 || selectedImage.value)
));

async function scrollTranscriptToBottom() {
  await nextTick();
  const element = transcriptRef.value;
  if (element) {
    element.scrollTop = element.scrollHeight;
  }
}

function handleImageSelect(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
  if (!allowedTypes.includes(file.type)) {
    error.value = 'Only JPG, PNG, GIF, and WebP images are allowed.';
    return;
  }

  const maxSize = 5 * 1024 * 1024; // 5MB
  if (file.size > maxSize) {
    error.value = 'Image must be smaller than 5MB.';
    return;
  }

  if (imagePreview.value) {
    URL.revokeObjectURL(imagePreview.value);
  }
  selectedImage.value = file;
  imagePreview.value = URL.createObjectURL(file);
  error.value = '';
}

function removeImage({ revoke = true } = {}) {
  if (revoke && imagePreview.value) {
    URL.revokeObjectURL(imagePreview.value);
  }
  selectedImage.value = null;
  imagePreview.value = null;
  if (imageInputRef.value) {
    imageInputRef.value.value = '';
  }
}

async function sendMessage() {
  const message = prompt.value.trim();
  if ((!message && !selectedImage.value) || loading.value || !isAuthenticated.value) {
    return;
  }

  const localImageUrl = imagePreview.value;
  const userMessage = {
    role: 'user',
    content: message || '(Image attached)',
    imageUrl: localImageUrl,
  };
  messages.value.push(userMessage);
  const imageFile = selectedImage.value;
  prompt.value = '';
  removeImage({ revoke: false });
  loading.value = true;
  error.value = '';

  messages.value.push({ role: 'assistant', content: 'Thinking from the indexed chunks...' });
  await scrollTranscriptToBottom();

  try {
    const response = await chatWithAssistant(message || '(Image attached)', imageFile);
    messages.value.pop();
    messages.value.push({ role: 'assistant', content: response.answer });
    queryVariations.value = response.query_variations ?? [];
    sources.value = response.sources ?? [];
    if (response.image_url) {
      userMessage.imageUrl = response.image_url;
    }
    if (localImageUrl) {
      URL.revokeObjectURL(localImageUrl);
    }
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
  if (loading.value) {
    return;
  }

  messages.value = defaultMessages();
  prompt.value = '';
  error.value = '';
  queryVariations.value = [];
  sources.value = [];
  removeImage();
}

function useSuggestion(suggestion) {
  prompt.value = suggestion;
}

function formatMessageContent(content) {
  if (!content) return '';
  // Escape HTML to prevent XSS issues
  let escaped = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  // Replace double asterisks **text** with <strong>text</strong>
  escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

  // Replace single asterisks *text* with <em>text</em>
  escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');

  // Convert inline code `code` to <code class="chat-inline-code">code</code>
  escaped = escaped.replace(/`(.*?)`/g, '<code class="chat-inline-code">$1</code>');

  return escaped;
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
          <button class="btn" type="button" :disabled="loading" @click="clearConversation">Clear</button>
        </div>

        <div ref="transcriptRef" class="assistant-chat__log">
          <template v-if="messages.length > 0">
            <article v-for="(message, index) in messages" :key="`${message.role}-${index}`" class="assistant-message"
              :class="message.role === 'user' ? 'assistant-message--user' : 'assistant-message--assistant'">
              <span class="assistant-message__role">{{ message.role === 'user' ? 'You' : 'Assistant' }}</span>
              <div class="assistant-message__text">
                <img v-if="message.imageUrl" :src="message.imageUrl" class="assistant-message__image" alt="Uploaded image" />
                <span v-html="formatMessageContent(message.content)"></span>
              </div>
            </article>
          </template>

          <div v-else class="assistant-empty">
            <strong>Start a conversation.</strong>
            <span>Try asking for a summary, a fact, or an image/table found in the chunks.</span>
          </div>
        </div>

        <form class="assistant-form" @submit.prevent="sendMessage"> 
          <div v-if="imagePreview" class="image-preview">
            <img :src="imagePreview" alt="Selected image preview" />
            <button class="image-preview__remove" type="button" @click="removeImage" title="Remove image">&times;</button>
          </div>
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
            <label class="btn btn--icon" title="Attach image (JPG, PNG, GIF, WebP, max 5MB)">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
              </svg>
              <input ref="imageInputRef" type="file" accept="image/jpeg,image/png,image/gif,image/webp" hidden @change="handleImageSelect" />
            </label>
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
