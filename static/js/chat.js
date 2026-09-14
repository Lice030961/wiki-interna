// Widget de chat flutuante (assistente da wiki)
const chatToggle = document.getElementById('chat-toggle');
const chatPanel = document.getElementById('chat-panel');
const chatClose = document.getElementById('chat-close');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');

const MAX_HISTORY_TURNS = 3; // "poucas mensagens" — espelha MAX_HISTORY_TURNS em core/chatbot.py
let chatHistory = []; // [{role: 'user'|'assistant', content}], só em memória (zera ao recarregar a página)

function pushHistory(role, content) {
  chatHistory.push({ role, content });
  chatHistory = chatHistory.slice(-MAX_HISTORY_TURNS * 2);
}

function getCsrfToken() {
  const input = chatForm.querySelector('input[name=csrfmiddlewaretoken]');
  return input ? input.value : null;
}

function addMessage(text, from, sources) {
  const bubble = document.createElement('div');
  bubble.className = from === 'user'
    ? 'ml-auto bg-brand-yellow/20 text-gray-900 rounded-lg px-3 py-2 max-w-[85%] whitespace-pre-wrap'
    : 'bg-gray-100 text-gray-900 rounded-lg px-3 py-2 max-w-[85%] whitespace-pre-wrap';
  bubble.textContent = text;
  chatMessages.appendChild(bubble);

  if (sources && sources.length) {
    const links = document.createElement('div');
    links.className = 'flex flex-col gap-1 max-w-[85%]';
    links.innerHTML = sources.map(s =>
      `<a href="${s.url}" class="text-xs text-brand-red hover:underline">🔗 ${s.title}</a>`
    ).join('');
    chatMessages.appendChild(links);
  }

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addTyping() {
  const bubble = document.createElement('div');
  bubble.id = 'chat-typing';
  bubble.className = 'bg-gray-100 rounded-lg px-3 py-2 w-fit typing-dots';
  bubble.innerHTML = '<span></span><span></span><span></span>';
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTyping() {
  const el = document.getElementById('chat-typing');
  if (el) el.remove();
}

if (chatToggle) {
  chatToggle.addEventListener('click', () => {
    chatPanel.classList.toggle('hidden');
    if (!chatPanel.classList.contains('hidden') && !chatMessages.children.length) {
      addMessage('Oi! Pergunte algo sobre os conteúdos da wiki.', 'bot');
    }
  });

  chatClose.addEventListener('click', () => chatPanel.classList.add('hidden'));

  chatForm.addEventListener('submit', e => {
    e.preventDefault();
    const question = chatInput.value.trim();
    if (!question) return;

    addMessage(question, 'user');
    chatInput.value = '';
    chatInput.disabled = true;
    addTyping();

    fetch('/chat/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ question, history: chatHistory }),
    })
      .then(r => r.json())
      .then(data => {
        removeTyping();
        if (data.error) {
          addMessage(data.error, 'bot');
        } else {
          addMessage(data.answer, 'bot', data.sources);
          pushHistory('user', question);
          pushHistory('assistant', data.answer);
        }
      })
      .catch(() => {
        removeTyping();
        addMessage('Erro ao falar com o assistente. Tenta de novo.', 'bot');
      })
      .finally(() => { chatInput.disabled = false; chatInput.focus(); });
  });
}
