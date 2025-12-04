/**
 * API Client for Pi-hole Wizard
 */

const API = {
    baseUrl: '',

    async get(endpoint) {
        const response = await fetch(`${this.baseUrl}${endpoint}`);
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }
        return response.json();
    },

    async post(endpoint, data) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }
        return response.json();
    },

    async patch(endpoint, data) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }
        return response.json();
    },

    async delete(endpoint) {
        const response = await fetch(`${this.baseUrl}${endpoint}`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(error.detail || 'Request failed');
        }
        return response.json();
    },

    // Prerequisites
    async checkPrerequisites() {
        return this.get('/api/prerequisites');
    },

    async detectNetwork() {
        return this.get('/api/prerequisites/network');
    },

    // Wizard State
    async getWizardState() {
        return this.get('/api/wizard/state');
    },

    async updateWizardState(state) {
        return this.post('/api/wizard/state', state);
    },

    async patchWizardState(updates) {
        return this.patch('/api/wizard/state', updates);
    },

    async resetWizardState() {
        return this.delete('/api/wizard/state');
    },

    async exportConfig() {
        const response = await fetch('/api/wizard/export');
        if (!response.ok) {
            throw new Error('Export failed');
        }
        return response.json();
    },

    async importConfig(configData) {
        return this.post('/api/wizard/import', configData);
    },

    // Config
    async previewConfig(state) {
        return this.post('/api/config/preview', state);
    },

    async generateConfig(state) {
        return this.post('/api/config/generate', state);
    },

    async downloadConfig(state) {
        const response = await fetch('/api/config/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(state),
        });
        if (!response.ok) {
            throw new Error('Download failed');
        }
        return response.blob();
    },

    // Installation
    async startInstallation(state) {
        return this.post('/api/install/start', state);
    },

    async getInstallStatus() {
        return this.get('/api/install/status');
    },

    connectInstallWebSocket(onMessage, onComplete, onError) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/api/install/ws`);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'log') {
                onMessage(data.message);
            } else if (data.type === 'complete') {
                onComplete(data);
            } else if (data.type === 'error') {
                onError(data.message);
            }
        };

        ws.onerror = () => {
            onError('WebSocket connection failed');
        };

        ws.onclose = () => {
            console.log('Installation WebSocket closed');
        };

        return ws;
    },

    // Update
    async checkForUpdates() {
        return this.get('/api/update/check');
    },

    async startUpdate() {
        return this.post('/api/update/start', {});
    },

    async getUpdateStatus() {
        return this.get('/api/update/status');
    },

    // Chat
    async sendChatMessage(message, apiKey) {
        return this.post('/api/chat/message', { message, api_key: apiKey });
    },

    async getChatHistory() {
        return this.get('/api/chat/history');
    },

    async clearChatHistory() {
        return this.delete('/api/chat/history');
    },

    async getQuickPrompts() {
        return this.get('/api/chat/quick-prompts');
    },

    // Blocklists
    async fetchBlocklistSample(listId) {
        return this.get(`/api/blocklists/${listId}/sample`);
    },

    // SSH Connection
    async getSSHStatus() {
        return this.get('/api/ssh/status');
    },

    async connectSSH(host, username, password, port = 22) {
        return this.post('/api/ssh/connect', { host, username, password, port });
    },

    async disconnectSSH() {
        return this.post('/api/ssh/disconnect', {});
    },

    async testSSHConnection() {
        return this.get('/api/ssh/test');
    },

    async checkRemoteDocker() {
        return this.get('/api/ssh/check-docker');
    },

    // Stats
    async getStats() {
        return this.get('/api/stats');
    },
};
