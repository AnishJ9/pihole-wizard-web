/**
 * Pi-hole Wizard - AI Chat Feature
 */

class ChatManager {
    constructor() {
        this.apiKey = localStorage.getItem('anthropic_api_key') || '';
        this.isOpen = false;
        this.init();
    }

    init() {
        this.bindEvents();
        this.updateApiKeyUI();
    }

    bindEvents() {
        // Open/close chat
        document.getElementById('chatBtn').addEventListener('click', () => this.toggleChat());
        document.getElementById('closeChatBtn').addEventListener('click', () => this.closeChat());
        document.getElementById('chatOverlay').addEventListener('click', () => this.closeChat());

        // API key
        document.getElementById('saveApiKey').addEventListener('click', () => this.saveApiKey());
        document.getElementById('apiKeyInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.saveApiKey();
        });

        // Send message
        document.getElementById('sendChatBtn').addEventListener('click', () => this.sendMessage());
        document.getElementById('chatInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Quick prompts
        document.querySelectorAll('.quick-prompt').forEach(btn => {
            btn.addEventListener('click', () => {
                document.getElementById('chatInput').value = btn.dataset.prompt;
                this.sendMessage();
            });
        });
    }

    toggleChat() {
        if (this.isOpen) {
            this.closeChat();
        } else {
            this.openChat();
        }
    }

    openChat() {
        this.isOpen = true;
        document.getElementById('chatSidebar').classList.add('open');
        document.getElementById('chatOverlay').classList.add('open');
        document.getElementById('chatInput').focus();
    }

    closeChat() {
        this.isOpen = false;
        document.getElementById('chatSidebar').classList.remove('open');
        document.getElementById('chatOverlay').classList.remove('open');
    }

    updateApiKeyUI() {
        const section = document.getElementById('apiKeySection');
        const quickPrompts = document.getElementById('quickPrompts');
        const input = document.getElementById('apiKeyInput');

        if (this.apiKey) {
            section.style.display = 'none';
            quickPrompts.style.display = 'flex';
            input.value = '';
        } else {
            section.style.display = 'block';
            quickPrompts.style.display = 'none';
        }
    }

    saveApiKey() {
        const input = document.getElementById('apiKeyInput');
        const key = input.value.trim();

        if (!key) {
            alert('Please enter your API key');
            return;
        }

        if (!key.startsWith('sk-ant-')) {
            alert('Invalid API key format. Anthropic API keys start with "sk-ant-"');
            return;
        }

        this.apiKey = key;
        localStorage.setItem('anthropic_api_key', key);
        this.updateApiKeyUI();
    }

    async sendMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();

        if (!message) return;

        if (!this.apiKey) {
            alert('Please enter your Anthropic API key first');
            return;
        }

        // Clear input
        input.value = '';

        // Add user message to chat
        this.addMessage(message, 'user');

        // Create streaming message container
        const messageId = this.addStreamingMessage();

        try {
            const response = await fetch('/api/chat/message/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, api_key: this.apiKey })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.text) {
                                fullText += data.text;
                                this.updateStreamingMessage(messageId, fullText);
                            } else if (data.error) {
                                if (data.error.includes('Invalid API key')) {
                                    this.apiKey = '';
                                    localStorage.removeItem('anthropic_api_key');
                                    this.updateApiKeyUI();
                                }
                                this.updateStreamingMessage(messageId, 'Error: ' + data.error);
                            }
                        } catch (e) {
                            // Ignore JSON parse errors for incomplete chunks
                        }
                    }
                }
            }

            // Final render with syntax highlighting
            this.finalizeStreamingMessage(messageId, fullText);

        } catch (e) {
            if (e.message.includes('401')) {
                this.apiKey = '';
                localStorage.removeItem('anthropic_api_key');
                this.updateApiKeyUI();
                this.updateStreamingMessage(messageId, 'Invalid API key. Please enter a valid key.');
            } else {
                this.updateStreamingMessage(messageId, 'Error: ' + e.message);
            }
        }
    }

    addMessage(content, role) {
        const container = document.getElementById('chatMessages');
        const message = document.createElement('div');
        message.className = `chat-message ${role}`;
        message.id = `msg-${Date.now()}`;

        if (role === 'assistant') {
            // Render markdown for assistant messages
            message.innerHTML = marked.parse(content);
            // Highlight code blocks
            message.querySelectorAll('pre code').forEach(block => {
                Prism.highlightElement(block);
            });
        } else {
            message.innerHTML = `<p>${this.escapeHtml(content)}</p>`;
        }

        container.appendChild(message);
        container.scrollTop = container.scrollHeight;

        return message.id;
    }

    addStreamingMessage() {
        const container = document.getElementById('chatMessages');
        const message = document.createElement('div');
        message.className = 'chat-message assistant streaming';
        message.id = `msg-stream-${Date.now()}`;
        message.innerHTML = '<p><span class="cursor">|</span></p>';
        container.appendChild(message);
        container.scrollTop = container.scrollHeight;
        return message.id;
    }

    updateStreamingMessage(id, content) {
        const message = document.getElementById(id);
        if (message) {
            // Simple text update while streaming (no markdown yet)
            message.innerHTML = `<p>${this.escapeHtml(content)}<span class="cursor">|</span></p>`;
            const container = document.getElementById('chatMessages');
            container.scrollTop = container.scrollHeight;
        }
    }

    finalizeStreamingMessage(id, content) {
        const message = document.getElementById(id);
        if (message) {
            message.classList.remove('streaming');
            // Render markdown and highlight code
            message.innerHTML = marked.parse(content);
            message.querySelectorAll('pre code').forEach(block => {
                Prism.highlightElement(block);
            });
            const container = document.getElementById('chatMessages');
            container.scrollTop = container.scrollHeight;
        }
    }

    addLoadingMessage() {
        const container = document.getElementById('chatMessages');
        const message = document.createElement('div');
        message.className = 'chat-message assistant';
        message.id = `msg-loading-${Date.now()}`;
        message.innerHTML = '<p><span class="spinner" style="display: inline-block; width: 1rem; height: 1rem;"></span> Thinking...</p>';
        container.appendChild(message);
        container.scrollTop = container.scrollHeight;
        return message.id;
    }

    removeMessage(id) {
        const message = document.getElementById(id);
        if (message) {
            message.remove();
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize chat when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.chat = new ChatManager();
});
