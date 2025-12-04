/**
 * Pi-hole Wizard - Main Application Logic
 */

class WizardApp {
    constructor() {
        this.currentStep = 1;
        this.totalSteps = 7;
        this.state = {
            deployment: 'docker',
            os: null,
            pihole_ip: null,
            network_interface: null,
            upstream_dns: 'unbound',
            enable_unbound: true,
            web_password: null,
            ipv6: false,
            dhcp_enabled: false,
            dhcp_start: null,
            dhcp_end: null,
            dhcp_router: null,
            custom_dns: null,
        };
        this.configPreview = null;
        this.installWs = null;

        this.init();
    }

    async init() {
        this.bindEvents();
        await this.loadSavedState();
        this.updateUI();
        await this.runPrerequisiteChecks();
    }

    bindEvents() {
        // Navigation
        document.getElementById('nextBtn').addEventListener('click', () => this.nextStep());
        document.getElementById('backBtn').addEventListener('click', () => this.prevStep());

        // Step indicators
        document.querySelectorAll('.step').forEach(step => {
            step.addEventListener('click', () => {
                const stepNum = parseInt(step.dataset.step);
                if (stepNum <= this.currentStep) {
                    this.goToStep(stepNum);
                }
            });
        });

        // Deployment type
        document.querySelectorAll('input[name="deployment"]').forEach(input => {
            input.addEventListener('change', (e) => {
                this.state.deployment = e.target.value;
                this.updateDeploymentUI();
                this.updateOptionCards();
            });
        });

        // Unbound toggle
        document.getElementById('enableUnbound').addEventListener('change', (e) => {
            this.state.enable_unbound = e.target.checked;
            this.updateDnsUI();
        });

        // Upstream DNS
        document.getElementById('upstreamDnsSelect').addEventListener('change', (e) => {
            this.state.upstream_dns = e.target.value;
            this.updateCustomDnsUI();
        });

        // IPv6 toggle
        document.getElementById('ipv6').addEventListener('change', (e) => {
            this.state.ipv6 = e.target.checked;
        });

        // DHCP toggle
        document.getElementById('dhcpEnabled').addEventListener('change', (e) => {
            this.state.dhcp_enabled = e.target.checked;
            this.updateDhcpUI();
        });

        // Password toggle
        document.getElementById('togglePassword').addEventListener('click', () => {
            const input = document.getElementById('webPassword');
            input.type = input.type === 'password' ? 'text' : 'password';
        });

        // Re-check prerequisites
        document.getElementById('recheckBtn').addEventListener('click', () => {
            this.runPrerequisiteChecks();
        });

        // Config tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.showConfigTab(tab.dataset.tab);
            });
        });

        // Download configs
        document.getElementById('downloadBtn').addEventListener('click', () => this.downloadConfigs());

        // One-click install
        document.getElementById('installBtn').addEventListener('click', () => this.startInstallation());

        // Cancel install
        document.getElementById('cancelInstall').addEventListener('click', () => this.cancelInstallation());

        // Continue to dashboard
        document.getElementById('continueToDashboard').addEventListener('click', () => {
            window.open(document.getElementById('dashboardLink').href, '_blank');
        });
    }

    async loadSavedState() {
        try {
            const savedState = await API.getWizardState();
            if (savedState) {
                this.state = { ...this.state, ...savedState };
            }
        } catch (e) {
            console.log('No saved state found');
        }
    }

    async saveState() {
        try {
            await API.updateWizardState(this.state);
        } catch (e) {
            console.error('Failed to save state:', e);
        }
    }

    updateUI() {
        // Update step indicators
        document.querySelectorAll('.step').forEach(step => {
            const stepNum = parseInt(step.dataset.step);
            step.classList.remove('active', 'completed');
            if (stepNum === this.currentStep) {
                step.classList.add('active');
            } else if (stepNum < this.currentStep) {
                step.classList.add('completed');
            }
        });

        // Update step content
        document.querySelectorAll('.step-content').forEach(content => {
            content.classList.remove('active');
        });
        const activeContent = document.querySelector(`.step-content[data-step="${this.currentStep}"]`);
        if (activeContent) {
            activeContent.classList.add('active');
        }

        // Update navigation buttons
        document.getElementById('backBtn').disabled = this.currentStep === 1;
        const nextBtn = document.getElementById('nextBtn');
        nextBtn.textContent = this.currentStep === this.totalSteps ? 'Finish' : 'Next';

        // Update footer visibility
        const footer = document.querySelector('.nav-footer');
        const installProgress = document.getElementById('installProgress');
        const successScreen = document.getElementById('successScreen');
        footer.style.display = installProgress.classList.contains('active') ||
                               successScreen.classList.contains('active') ? 'none' : 'flex';
    }

    updateOptionCards() {
        document.querySelectorAll('.option-card').forEach(card => {
            const input = card.querySelector('input');
            card.classList.toggle('selected', input.checked);
        });
    }

    updateDeploymentUI() {
        const osSelect = document.getElementById('osSelect');
        const interfaceGroup = document.getElementById('interfaceGroup');

        if (this.state.deployment === 'bare-metal') {
            osSelect.style.display = 'block';
            interfaceGroup.style.display = 'block';
        } else {
            osSelect.style.display = 'none';
            interfaceGroup.style.display = 'none';
        }
    }

    updateDnsUI() {
        const upstreamDns = document.getElementById('upstreamDns');
        upstreamDns.style.display = this.state.enable_unbound ? 'none' : 'block';
        this.updateCustomDnsUI();
    }

    updateCustomDnsUI() {
        const customDns = document.getElementById('customDns');
        customDns.style.display =
            !this.state.enable_unbound && this.state.upstream_dns === 'custom' ? 'block' : 'none';
    }

    updateDhcpUI() {
        const dhcpSettings = document.getElementById('dhcpSettings');
        dhcpSettings.style.display = this.state.dhcp_enabled ? 'block' : 'none';
    }

    async runPrerequisiteChecks() {
        const container = document.getElementById('prereqChecks');
        container.innerHTML = `
            <div class="prereq-card checking">
                <div class="prereq-icon"><div class="spinner"></div></div>
                <div class="prereq-info">
                    <h3>Checking system...</h3>
                    <p>Please wait</p>
                </div>
            </div>
        `;

        try {
            const result = await API.checkPrerequisites();
            this.renderPrerequisites(result);

            // Auto-fill detected network info
            if (result.detected_ip && !this.state.pihole_ip) {
                this.state.pihole_ip = result.detected_ip;
                document.getElementById('piholeIp').value = result.detected_ip;
                document.getElementById('detectedIp').textContent = `Detected: ${result.detected_ip}`;
            }
            if (result.detected_interface) {
                this.state.network_interface = result.detected_interface;
                document.getElementById('networkInterface').value = result.detected_interface;
            }
            if (result.detected_gateway) {
                this.state.dhcp_router = result.detected_gateway;
                document.getElementById('dhcpRouter').value = result.detected_gateway;
            }

            // Auto-suggest DHCP range
            if (result.detected_ip) {
                const prefix = result.detected_ip.split('.').slice(0, 3).join('.');
                if (!this.state.dhcp_start) {
                    this.state.dhcp_start = `${prefix}.100`;
                    document.getElementById('dhcpStart').value = this.state.dhcp_start;
                }
                if (!this.state.dhcp_end) {
                    this.state.dhcp_end = `${prefix}.200`;
                    document.getElementById('dhcpEnd').value = this.state.dhcp_end;
                }
            }

        } catch (e) {
            container.innerHTML = `
                <div class="prereq-card fail">
                    <div class="prereq-icon">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                        </svg>
                    </div>
                    <div class="prereq-info">
                        <h3>Check failed</h3>
                        <p>${e.message}</p>
                    </div>
                </div>
            `;
        }

        document.getElementById('recheckBtn').style.display = 'block';
    }

    renderPrerequisites(result) {
        const container = document.getElementById('prereqChecks');
        container.innerHTML = '';

        const iconMap = {
            pass: `<svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`,
            fail: `<svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`,
            warning: `<svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>`,
        };

        result.checks.forEach(check => {
            const card = document.createElement('div');
            card.className = `prereq-card ${check.status}`;
            card.innerHTML = `
                <div class="prereq-icon">${iconMap[check.status]}</div>
                <div class="prereq-info">
                    <h3>${check.name}</h3>
                    <p>${check.message}</p>
                    ${check.details ? `<p class="help-text">${check.details}</p>` : ''}
                    ${check.fix_suggestion ? `<p class="prereq-fix">${check.fix_suggestion}</p>` : ''}
                </div>
            `;
            container.appendChild(card);
        });
    }

    collectFormData() {
        // Collect data from current step's form
        const step = this.currentStep;

        if (step === 2) {
            this.state.deployment = document.querySelector('input[name="deployment"]:checked')?.value || 'docker';
            if (this.state.deployment === 'bare-metal') {
                this.state.os = document.getElementById('os').value;
            }
        } else if (step === 3) {
            this.state.pihole_ip = document.getElementById('piholeIp').value;
            this.state.network_interface = document.getElementById('networkInterface').value;
        } else if (step === 4) {
            this.state.enable_unbound = document.getElementById('enableUnbound').checked;
            this.state.ipv6 = document.getElementById('ipv6').checked;
            if (!this.state.enable_unbound) {
                this.state.upstream_dns = document.getElementById('upstreamDnsSelect').value;
                if (this.state.upstream_dns === 'custom') {
                    this.state.custom_dns = document.getElementById('customDnsInput').value;
                }
            }
        } else if (step === 5) {
            this.state.dhcp_enabled = document.getElementById('dhcpEnabled').checked;
            if (this.state.dhcp_enabled) {
                this.state.dhcp_start = document.getElementById('dhcpStart').value;
                this.state.dhcp_end = document.getElementById('dhcpEnd').value;
                this.state.dhcp_router = document.getElementById('dhcpRouter').value;
            }
        } else if (step === 6) {
            const password = document.getElementById('webPassword').value;
            const confirm = document.getElementById('webPasswordConfirm').value;
            if (password && password !== confirm) {
                document.getElementById('passwordError').style.display = 'block';
                return false;
            }
            document.getElementById('passwordError').style.display = 'none';
            this.state.web_password = password;
        }

        return true;
    }

    async nextStep() {
        if (!this.collectFormData()) {
            return;
        }

        await this.saveState();

        if (this.currentStep < this.totalSteps) {
            this.currentStep++;
            this.updateUI();

            // Load config preview on review step
            if (this.currentStep === 7) {
                await this.loadConfigPreview();
            }
        }
    }

    prevStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.updateUI();
        }
    }

    goToStep(step) {
        this.collectFormData();
        this.currentStep = step;
        this.updateUI();

        if (step === 7) {
            this.loadConfigPreview();
        }
    }

    async loadConfigPreview() {
        try {
            this.configPreview = await API.previewConfig(this.state);
            this.renderSummary();
            this.showConfigTab('docker-compose');
            this.renderCommands();
        } catch (e) {
            console.error('Failed to load config preview:', e);
        }
    }

    renderSummary() {
        const table = document.getElementById('summaryTable').querySelector('tbody');
        table.innerHTML = '';

        const rows = [
            ['Deployment', this.state.deployment === 'docker' ? 'Docker' : 'Bare Metal'],
            ['Pi-hole IP', this.state.pihole_ip || 'Not set'],
            ['DNS Resolver', this.state.enable_unbound ? 'Unbound (Recursive)' : this.state.upstream_dns],
            ['IPv6', this.state.ipv6 ? 'Enabled' : 'Disabled'],
            ['DHCP Server', this.state.dhcp_enabled ? 'Enabled' : 'Disabled'],
            ['Web Password', this.state.web_password ? 'Set' : 'Not set'],
        ];

        if (this.state.dhcp_enabled) {
            rows.push(['DHCP Range', `${this.state.dhcp_start} - ${this.state.dhcp_end}`]);
        }

        rows.forEach(([label, value]) => {
            const row = document.createElement('tr');
            row.innerHTML = `<td>${label}</td><td>${value}</td>`;
            table.appendChild(row);
        });
    }

    showConfigTab(tabName) {
        if (!this.configPreview) return;

        const fileMap = {
            'docker-compose': 'docker-compose.yml',
            'env': '.env',
            'unbound': 'unbound/pi-hole.conf',
        };

        const filename = fileMap[tabName];
        const file = this.configPreview.files.find(f => f.filename === filename);

        const preview = document.getElementById('configPreview');
        const code = preview.querySelector('code');

        if (file) {
            code.textContent = file.content;
            code.className = tabName === 'docker-compose' ? 'language-yaml' :
                             tabName === 'unbound' ? 'language-ini' : 'language-bash';
        } else {
            code.textContent = 'Not applicable for current configuration.';
            code.className = '';
        }

        Prism.highlightElement(code);
    }

    renderCommands() {
        if (!this.configPreview) return;

        const preview = document.getElementById('commandsPreview');
        const code = preview.querySelector('code');
        code.textContent = this.configPreview.commands_to_run.join('\n');
        Prism.highlightElement(code);
    }

    async downloadConfigs() {
        try {
            const blob = await API.downloadConfig(this.state);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'pihole-config.zip';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (e) {
            alert('Download failed: ' + e.message);
        }
    }

    async startInstallation() {
        // Hide wizard, show progress
        document.querySelector(`.step-content[data-step="7"]`).classList.remove('active');
        document.getElementById('installProgress').classList.add('active');
        document.querySelector('.nav-footer').style.display = 'none';

        const logsEl = document.getElementById('installLogs');
        const progressBar = document.getElementById('installProgressBar');
        const stepEl = document.getElementById('installStep');

        logsEl.textContent = '';

        try {
            // Start installation
            await API.startInstallation(this.state);

            // Connect WebSocket for logs
            this.installWs = API.connectInstallWebSocket(
                (message) => {
                    logsEl.textContent += message;
                    logsEl.scrollTop = logsEl.scrollHeight;
                },
                (result) => {
                    if (result.status === 'success') {
                        this.showSuccessScreen();
                    } else {
                        stepEl.textContent = 'Installation failed: ' + result.message;
                        progressBar.style.background = 'var(--error)';
                    }
                },
                (error) => {
                    stepEl.textContent = 'Error: ' + error;
                    progressBar.style.background = 'var(--error)';
                }
            );

            // Poll for status updates
            const statusInterval = setInterval(async () => {
                try {
                    const status = await API.getInstallStatus();
                    progressBar.style.width = `${status.progress}%`;
                    stepEl.textContent = status.current_step;

                    if (status.status !== 'running') {
                        clearInterval(statusInterval);
                    }
                } catch (e) {
                    clearInterval(statusInterval);
                }
            }, 1000);

        } catch (e) {
            stepEl.textContent = 'Failed to start: ' + e.message;
        }
    }

    cancelInstallation() {
        if (this.installWs) {
            this.installWs.close();
        }
        document.getElementById('installProgress').classList.remove('active');
        document.querySelector(`.step-content[data-step="7"]`).classList.add('active');
        document.querySelector('.nav-footer').style.display = 'flex';
    }

    showSuccessScreen() {
        document.getElementById('installProgress').classList.remove('active');
        document.getElementById('successScreen').classList.add('active');

        const dashboardLink = document.getElementById('dashboardLink');
        dashboardLink.href = `http://${this.state.pihole_ip}/admin`;
        dashboardLink.textContent = `http://${this.state.pihole_ip}/admin`;
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new WizardApp();
});
