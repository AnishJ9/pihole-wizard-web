/**
 * Pi-hole Wizard - Main Application Logic
 */

class WizardApp {
    constructor() {
        this.currentStep = 1;
        this.totalSteps = 7;
        this.theme = localStorage.getItem('theme') || 'dark';
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
            blocklists: ['stevenblack'],
        };

        // Blocklist definitions with metadata
        this.blocklistDefinitions = {
            'stevenblack': {
                name: 'StevenBlack Unified',
                description: 'Comprehensive hosts file combining multiple sources.',
                url: 'https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts',
                badge: 'default',
                badgeText: 'Default',
                estimatedDomains: '~130k'
            },
            'oisd': {
                name: 'OISD Big',
                description: 'One of the most popular lists. Blocks ads, trackers, malware.',
                url: 'https://big.oisd.nl/domainswild',
                badge: 'popular',
                badgeText: 'Popular',
                estimatedDomains: '~200k'
            },
            'hagezi': {
                name: 'Hagezi Multi Pro',
                description: 'Balanced list for ads, tracking, analytics, and telemetry.',
                url: 'https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/pro.txt',
                badge: 'popular',
                badgeText: 'Popular',
                estimatedDomains: '~300k'
            },
            'firebog-ticked': {
                name: 'Firebog Ticked Lists',
                description: 'Curated collection of safe-to-use lists from The Firebog.',
                url: 'https://v.firebog.net/hosts/lists.php?type=tick',
                badge: null,
                estimatedDomains: '~500k'
            },
            'adguard-dns': {
                name: 'AdGuard DNS Filter',
                description: "AdGuard's curated filter for DNS-level blocking.",
                url: 'https://adguardteam.github.io/AdGuardSDNSFilter/Filters/filter.txt',
                badge: null,
                estimatedDomains: '~50k'
            },
            'nocoin': {
                name: 'NoCoin + Malware',
                description: 'Blocks cryptocurrency miners and malware domains.',
                url: 'https://raw.githubusercontent.com/hoshsadiq/adblock-nocoin-list/master/hosts.txt',
                badge: null,
                estimatedDomains: '~10k'
            }
        };

        // Blocklist URLs mapping (keep for backward compatibility)
        this.blocklistUrls = Object.fromEntries(
            Object.entries(this.blocklistDefinitions).map(([k, v]) => [k, v.url])
        );

        // Store for loaded domains and customizations
        this.blocklistDomains = {}; // { listId: ['domain1.com', 'domain2.com', ...] }
        this.blocklistExclusions = {}; // { listId: ['excluded-domain.com', ...] }
        this.blocklistAdditions = {}; // { listId: ['added-domain.com', ...] }
        this.customBlocklists = []; // [{ id: 'custom-1', name: 'My List', domains: [...] }]

        this.configPreview = null;
        this.installWs = null;

        this.init();
    }

    async init() {
        this.applyTheme();
        this.bindEvents();
        await this.loadSavedState();
        this.renderBlocklists();
        this.updateUI();
        await this.runPrerequisiteChecks();
        await this.checkExistingInstallation();
    }

    async checkExistingInstallation() {
        // Check if Pi-hole is already installed to show/hide Update button
        try {
            const result = await API.checkForUpdates();
            if (result.has_existing_install) {
                document.getElementById('updateBtn').style.display = 'inline-flex';
            }
        } catch (e) {
            // Silently fail - just don't show the update button
            console.log('Could not check for existing installation:', e.message);
        }
    }

    // Theme management
    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        this.updateThemeIcon();
    }

    toggleTheme() {
        this.theme = this.theme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('theme', this.theme);
        this.applyTheme();
    }

    updateThemeIcon() {
        const darkIcon = document.getElementById('themeIconDark');
        const lightIcon = document.getElementById('themeIconLight');
        if (this.theme === 'dark') {
            darkIcon.style.display = 'block';
            lightIcon.style.display = 'none';
        } else {
            darkIcon.style.display = 'none';
            lightIcon.style.display = 'block';
        }
    }

    // Loading states
    showLoading(message = 'Loading...') {
        document.getElementById('loadingText').textContent = message;
        document.getElementById('loadingOverlay').classList.add('active');
    }

    hideLoading() {
        document.getElementById('loadingOverlay').classList.remove('active');
    }

    setButtonLoading(buttonId, loading = true) {
        const btn = document.getElementById(buttonId);
        if (btn) {
            if (loading) {
                btn.classList.add('loading');
                btn.disabled = true;
            } else {
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        }
    }

    // Keyboard navigation
    handleKeyboard(e) {
        // Don't navigate if user is typing in an input
        const activeEl = document.activeElement;
        if (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.tagName === 'SELECT') {
            return;
        }

        // Don't navigate if modal is open
        if (document.getElementById('updateModal').style.display === 'block' ||
            document.getElementById('chatSidebar').classList.contains('open')) {
            return;
        }

        // Don't navigate during install or success screens
        if (document.getElementById('installProgress').classList.contains('active') ||
            document.getElementById('successScreen').classList.contains('active')) {
            return;
        }

        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            e.preventDefault();
            this.nextStep();
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            e.preventDefault();
            this.prevStep();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            this.nextStep();
        }
    }

    bindEvents() {
        // Navigation
        document.getElementById('nextBtn').addEventListener('click', () => this.nextStep());
        document.getElementById('backBtn').addEventListener('click', () => this.prevStep());

        // Export/Import
        document.getElementById('exportBtn').addEventListener('click', () => this.exportConfig());
        document.getElementById('importBtn').addEventListener('click', () => {
            document.getElementById('importFileInput').click();
        });
        document.getElementById('importFileInput').addEventListener('change', (e) => this.importConfig(e));

        // Update modal
        document.getElementById('updateBtn').addEventListener('click', () => this.openUpdateModal());
        document.getElementById('closeUpdateModal').addEventListener('click', () => this.closeUpdateModal());
        document.getElementById('modalOverlay').addEventListener('click', () => this.closeUpdateModal());
        document.getElementById('checkUpdateBtn').addEventListener('click', () => this.checkForUpdates());
        document.getElementById('startUpdateBtn').addEventListener('click', () => this.startUpdate());

        // Theme toggle
        document.getElementById('themeToggle').addEventListener('click', () => this.toggleTheme());

        // Keyboard navigation
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));

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

        // Dismiss support banner
        document.getElementById('dismissBanner')?.addEventListener('click', () => {
            document.getElementById('supportBanner').style.display = 'none';
            localStorage.setItem('bannerDismissed', 'true');
        });

        // Dismiss security banner
        document.getElementById('dismissSecurityBanner')?.addEventListener('click', () => {
            document.getElementById('securityBanner').style.display = 'none';
            localStorage.setItem('securityBannerDismissed', 'true');
        });

        // Hide security banner if already dismissed
        if (localStorage.getItem('securityBannerDismissed') === 'true') {
            const securityBanner = document.getElementById('securityBanner');
            if (securityBanner) securityBanner.style.display = 'none';
        }

        // Config tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                this.showConfigTab(tab.dataset.tab);
            });
        });

        // Copy buttons
        document.getElementById('copyConfigBtn').addEventListener('click', () => this.copyConfig());
        document.getElementById('copyCommandsBtn').addEventListener('click', () => this.copyCommands());

        // Review page buttons
        document.getElementById('reviewBackBtn').addEventListener('click', () => this.prevStep());
        document.getElementById('downloadBtn').addEventListener('click', () => this.downloadConfigs());
        document.getElementById('installBtn').addEventListener('click', () => this.startInstallation());

        // Cancel install
        document.getElementById('cancelInstall').addEventListener('click', () => this.cancelInstallation());

        // Continue to dashboard
        document.getElementById('continueToDashboard').addEventListener('click', () => {
            window.open(document.getElementById('dashboardLink').href, '_blank');
        });

        // Custom blocklist button
        document.getElementById('addCustomBlocklist').addEventListener('click', () => {
            this.showCustomBlocklistForm();
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

    updateUI(direction = 'forward') {
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

        // Update step content with direction-aware animation
        const currentActive = document.querySelector('.step-content.active');
        const newContent = document.querySelector(`.step-content[data-step="${this.currentStep}"]`);

        // Animate out old content
        if (currentActive && currentActive !== newContent) {
            currentActive.classList.remove('active', 'slide-left');
            currentActive.classList.add('exiting');
            if (direction === 'back') {
                currentActive.classList.add('slide-left');
            }
            // Remove exiting class after animation
            setTimeout(() => {
                currentActive.classList.remove('exiting', 'slide-left');
            }, 350);
        }

        // Animate in new content
        if (newContent) {
            newContent.classList.remove('slide-left');
            if (direction === 'back') {
                newContent.classList.add('slide-left');
            }
            newContent.classList.add('active');
        }

        // Update navigation buttons
        document.getElementById('backBtn').disabled = this.currentStep === 1;
        const nextBtn = document.getElementById('nextBtn');
        nextBtn.textContent = 'Next';

        // Update footer visibility - hide on step 7 (review page has its own action buttons)
        const footer = document.querySelector('.nav-footer');
        const installProgress = document.getElementById('installProgress');
        const successScreen = document.getElementById('successScreen');
        const isReviewStep = this.currentStep === this.totalSteps;
        footer.style.display = installProgress.classList.contains('active') ||
                               successScreen.classList.contains('active') ||
                               isReviewStep ? 'none' : 'flex';
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

            // Show support banner if prerequisites passed and not previously dismissed
            const hasFailed = result.checks?.some(c => c.status === 'fail');
            if (!hasFailed && !localStorage.getItem('bannerDismissed')) {
                document.getElementById('supportBanner').style.display = 'flex';
            }

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

            // Show static IP warning if not confirmed static
            this.showStaticIpWarning(result.is_static_ip, result.static_ip_message);

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

    showStaticIpWarning(isStatic, message) {
        // Show warning in Step 3 (Network Configuration) if IP is not confirmed static
        const warningEl = document.getElementById('staticIpWarning');
        if (warningEl) {
            if (isStatic) {
                warningEl.innerHTML = `
                    <div class="info-box success">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                        </svg>
                        <span><strong>Static IP confirmed:</strong> ${message}</span>
                    </div>
                `;
            } else {
                warningEl.innerHTML = `
                    <div class="warning-box">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>
                        </svg>
                        <div>
                            <strong>Static IP not detected:</strong> ${message}
                            <p style="margin-top: 0.5rem; font-size: 0.875rem;">Pi-hole needs a static IP so devices can always find it. Either:</p>
                            <ul style="margin-top: 0.25rem; margin-left: 1.25rem; font-size: 0.875rem;">
                                <li>Set a static IP in your Pi's network settings, or</li>
                                <li>Create a DHCP reservation for this device on your router</li>
                            </ul>
                        </div>
                    </div>
                `;
            }
        }
    }

    // Blocklist Management Methods
    renderBlocklists() {
        const container = document.getElementById('blocklistPresets');
        container.innerHTML = '';

        // Render predefined blocklists
        for (const [id, def] of Object.entries(this.blocklistDefinitions)) {
            container.appendChild(this.createBlocklistCard(id, def, false));
        }

        // Render custom blocklists
        for (const custom of this.customBlocklists) {
            container.appendChild(this.createBlocklistCard(custom.id, {
                name: custom.name,
                description: custom.description || 'Custom blocklist',
                badge: 'custom',
                badgeText: 'Custom',
                estimatedDomains: `${custom.domains.length} domains`
            }, true, custom.domains));
        }
    }

    createBlocklistCard(id, def, isCustom = false, preloadedDomains = null) {
        const card = document.createElement('div');
        card.className = `blocklist-card-expandable${isCustom ? ' custom-list' : ''}`;
        card.dataset.listId = id;

        const isChecked = this.state.blocklists.includes(id);

        card.innerHTML = `
            <div class="blocklist-main-row">
                <input type="checkbox" class="blocklist-main-checkbox" name="blocklist" value="${id}" ${isChecked ? 'checked' : ''}>
                <div class="blocklist-main-content">
                    <div class="blocklist-main-header">
                        <strong>${def.name}</strong>
                        ${def.badge ? `<span class="blocklist-badge ${def.badge}">${def.badgeText}</span>` : ''}
                        <span class="domain-count-badge">${def.estimatedDomains}</span>
                    </div>
                    <p>${def.description}</p>
                </div>
                <button class="blocklist-expand-btn" title="View and customize domains">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                        <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
                    </svg>
                </button>
            </div>
            <div class="blocklist-domains-panel">
                <div class="blocklist-domains-header">
                    <span>Domains in this list</span>
                    <div class="blocklist-domains-actions">
                        <button class="select-all-btn">Select All</button>
                        <button class="deselect-all-btn">Deselect All</button>
                        ${isCustom ? '<button class="delete-list-btn" style="color: var(--error);">Delete List</button>' : ''}
                    </div>
                </div>
                <div class="blocklist-domains-list">
                    <div class="blocklist-loading">
                        <div class="spinner"></div>
                        <span>Click to load domains...</span>
                    </div>
                </div>
                <div class="blocklist-add-domain">
                    <input type="text" placeholder="Add custom domain (e.g., ads.example.com)" class="add-domain-input">
                    <button class="add-domain-btn">Add</button>
                </div>
            </div>
        `;

        // Store preloaded domains for custom lists
        if (preloadedDomains) {
            this.blocklistDomains[id] = preloadedDomains;
        }

        // Bind events
        this.bindBlocklistCardEvents(card, id, isCustom);

        return card;
    }

    bindBlocklistCardEvents(card, listId, isCustom) {
        const expandBtn = card.querySelector('.blocklist-expand-btn');
        const mainRow = card.querySelector('.blocklist-main-row');
        const checkbox = card.querySelector('.blocklist-main-checkbox');
        const domainsList = card.querySelector('.blocklist-domains-list');
        const addInput = card.querySelector('.add-domain-input');
        const addBtn = card.querySelector('.add-domain-btn');
        const selectAllBtn = card.querySelector('.select-all-btn');
        const deselectAllBtn = card.querySelector('.deselect-all-btn');
        const deleteBtn = card.querySelector('.delete-list-btn');

        // Toggle expand
        expandBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleBlocklistExpand(card, listId);
        });

        // Main row click toggles checkbox (but not when clicking expand)
        mainRow.addEventListener('click', (e) => {
            if (e.target !== expandBtn && !expandBtn.contains(e.target)) {
                checkbox.checked = !checkbox.checked;
                this.updateBlocklistState();
            }
        });

        // Checkbox change
        checkbox.addEventListener('change', () => {
            this.updateBlocklistState();
        });

        // Add domain
        addBtn.addEventListener('click', () => {
            this.addDomainToList(listId, addInput.value.trim());
            addInput.value = '';
        });

        addInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.addDomainToList(listId, addInput.value.trim());
                addInput.value = '';
            }
        });

        // Select/Deselect all
        selectAllBtn.addEventListener('click', () => {
            this.setAllDomainsInList(listId, true);
        });

        deselectAllBtn.addEventListener('click', () => {
            this.setAllDomainsInList(listId, false);
        });

        // Delete custom list
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => {
                this.deleteCustomBlocklist(listId);
            });
        }
    }

    async toggleBlocklistExpand(card, listId) {
        const isExpanded = card.classList.contains('expanded');

        if (isExpanded) {
            card.classList.remove('expanded');
        } else {
            card.classList.add('expanded');

            // Load domains if not already loaded
            if (!this.blocklistDomains[listId]) {
                await this.loadBlocklistDomains(listId);
            } else {
                this.renderDomainsList(listId);
            }
        }
    }

    async loadBlocklistDomains(listId) {
        const card = document.querySelector(`[data-list-id="${listId}"]`);
        const domainsList = card.querySelector('.blocklist-domains-list');

        domainsList.innerHTML = `
            <div class="blocklist-loading">
                <div class="spinner"></div>
                <span>Loading domains...</span>
            </div>
        `;

        try {
            // For demo purposes, we'll fetch a sample of domains
            // In production, you'd want to fetch from the actual URL or use a backend proxy
            const def = this.blocklistDefinitions[listId];
            if (!def) {
                // Custom list already has domains loaded
                this.renderDomainsList(listId);
                return;
            }

            // Fetch sample domains (first 100 for display)
            const response = await API.fetchBlocklistSample(listId);
            this.blocklistDomains[listId] = response.domains || [];
            this.renderDomainsList(listId);
        } catch (e) {
            console.error('Failed to load blocklist domains:', e);
            // Show sample domains as fallback
            this.blocklistDomains[listId] = this.getSampleDomains(listId);
            this.renderDomainsList(listId);
        }
    }

    getSampleDomains(listId) {
        // Sample domains for demonstration (when API is not available)
        const samples = {
            'stevenblack': [
                'ads.google.com', 'pagead2.googlesyndication.com', 'ad.doubleclick.net',
                'tracking.example.com', 'analytics.facebook.com', 'pixel.facebook.com',
                'ads.twitter.com', 'advertising.amazon.com', 'adserver.example.net',
                'track.example.org', 'metrics.example.com', 'telemetry.microsoft.com'
            ],
            'oisd': [
                'ad.example.com', 'tracker.example.com', 'analytics.example.com',
                'pixel.tracking.com', 'ads.cdn.example.net', 'marketing.example.org',
                'beacon.example.com', 'stats.example.com', 'click.example.com'
            ],
            'hagezi': [
                'telemetry.example.com', 'analytics-api.example.com', 'data.collector.net',
                'tracking-pixel.example.org', 'user-metrics.example.com', 'ad-cdn.example.net'
            ],
            'firebog-ticked': [
                'malware.example.com', 'phishing.example.net', 'suspicious.example.org',
                'known-bad.example.com', 'threat.example.net', 'dangerous.example.org'
            ],
            'adguard-dns': [
                'ads.adguard-example.com', 'tracker.adguard-example.net',
                'banner.example.com', 'pop-up.example.net', 'interstitial.example.org'
            ],
            'nocoin': [
                'coinhive.com', 'coin-hive.com', 'cryptoloot.pro', 'crypto-miner.example.net',
                'miner.example.com', 'coin-pool.example.org', 'mining-script.example.net'
            ]
        };
        return samples[listId] || ['example-domain-1.com', 'example-domain-2.com', 'example-domain-3.com'];
    }

    renderDomainsList(listId) {
        const card = document.querySelector(`[data-list-id="${listId}"]`);
        const domainsList = card.querySelector('.blocklist-domains-list');
        const domains = this.blocklistDomains[listId] || [];
        const exclusions = this.blocklistExclusions[listId] || [];
        const additions = this.blocklistAdditions[listId] || [];

        // Combine original + additions
        const allDomains = [...domains, ...additions];

        if (allDomains.length === 0) {
            domainsList.innerHTML = `
                <div class="blocklist-loading">
                    <span>No domains loaded. Add custom domains below.</span>
                </div>
            `;
            return;
        }

        domainsList.innerHTML = allDomains.map(domain => {
            const isExcluded = exclusions.includes(domain);
            const isAddition = additions.includes(domain);
            return `
                <div class="blocklist-domain-item ${isExcluded ? 'excluded' : ''}" data-domain="${domain}">
                    <input type="checkbox" ${!isExcluded ? 'checked' : ''} class="domain-checkbox">
                    <span class="domain-text">${domain}</span>
                    ${isAddition ? `
                        <button class="remove-domain" title="Remove custom domain">
                            <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
                                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                            </svg>
                        </button>
                    ` : ''}
                </div>
            `;
        }).join('');

        // Bind domain checkbox events
        domainsList.querySelectorAll('.domain-checkbox').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const item = e.target.closest('.blocklist-domain-item');
                const domain = item.dataset.domain;
                this.toggleDomainExclusion(listId, domain, !e.target.checked);
            });
        });

        // Bind remove buttons
        domainsList.querySelectorAll('.remove-domain').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const item = e.target.closest('.blocklist-domain-item');
                const domain = item.dataset.domain;
                this.removeDomainFromList(listId, domain);
            });
        });

        // Update domain count badge
        const countBadge = card.querySelector('.domain-count-badge');
        const activeCount = allDomains.length - exclusions.length;
        countBadge.textContent = `${activeCount}/${allDomains.length} active`;
    }

    toggleDomainExclusion(listId, domain, exclude) {
        if (!this.blocklistExclusions[listId]) {
            this.blocklistExclusions[listId] = [];
        }

        if (exclude) {
            if (!this.blocklistExclusions[listId].includes(domain)) {
                this.blocklistExclusions[listId].push(domain);
            }
        } else {
            this.blocklistExclusions[listId] = this.blocklistExclusions[listId].filter(d => d !== domain);
        }

        // Update visual state
        const card = document.querySelector(`[data-list-id="${listId}"]`);
        const item = card.querySelector(`[data-domain="${domain}"]`);
        if (item) {
            item.classList.toggle('excluded', exclude);
        }

        this.renderDomainsList(listId);
    }

    addDomainToList(listId, domain) {
        if (!domain) return;

        // Validate domain format
        const domainRegex = /^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$/;
        if (!domainRegex.test(domain)) {
            alert('Please enter a valid domain name (e.g., ads.example.com)');
            return;
        }

        if (!this.blocklistAdditions[listId]) {
            this.blocklistAdditions[listId] = [];
        }

        if (!this.blocklistAdditions[listId].includes(domain)) {
            this.blocklistAdditions[listId].push(domain);
            this.renderDomainsList(listId);
        }
    }

    removeDomainFromList(listId, domain) {
        if (this.blocklistAdditions[listId]) {
            this.blocklistAdditions[listId] = this.blocklistAdditions[listId].filter(d => d !== domain);
            this.renderDomainsList(listId);
        }
    }

    setAllDomainsInList(listId, checked) {
        const domains = this.blocklistDomains[listId] || [];
        const additions = this.blocklistAdditions[listId] || [];
        const allDomains = [...domains, ...additions];

        if (checked) {
            // Clear all exclusions
            this.blocklistExclusions[listId] = [];
        } else {
            // Exclude all domains
            this.blocklistExclusions[listId] = [...allDomains];
        }

        this.renderDomainsList(listId);
    }

    updateBlocklistState() {
        // Collect selected blocklists
        this.state.blocklists = Array.from(
            document.querySelectorAll('.blocklist-main-checkbox:checked')
        ).map(cb => cb.value);
    }

    showCustomBlocklistForm() {
        // Check if form already exists
        let form = document.querySelector('.custom-blocklist-form');
        if (form) {
            form.classList.toggle('active');
            return;
        }

        // Create form
        form = document.createElement('div');
        form.className = 'custom-blocklist-form active';
        form.innerHTML = `
            <h4>Create Custom Blocklist</h4>
            <div class="form-group">
                <label>List Name</label>
                <input type="text" id="customListName" placeholder="My Custom Blocklist">
            </div>
            <div class="form-group">
                <label>Description (optional)</label>
                <input type="text" id="customListDescription" placeholder="Domains I want to block">
            </div>
            <div class="form-group">
                <label>Domains (one per line)</label>
                <textarea id="customListDomains" placeholder="ads.example.com&#10;tracking.example.net&#10;spam.example.org"></textarea>
            </div>
            <div class="form-actions">
                <button class="btn btn-secondary" id="cancelCustomList">Cancel</button>
                <button class="btn btn-primary" id="saveCustomList">Create List</button>
            </div>
        `;

        document.querySelector('.custom-blocklist-section').appendChild(form);

        // Bind form events
        document.getElementById('cancelCustomList').addEventListener('click', () => {
            form.classList.remove('active');
        });

        document.getElementById('saveCustomList').addEventListener('click', () => {
            this.saveCustomBlocklist();
        });
    }

    saveCustomBlocklist() {
        const name = document.getElementById('customListName').value.trim();
        const description = document.getElementById('customListDescription').value.trim();
        const domainsText = document.getElementById('customListDomains').value.trim();

        if (!name) {
            alert('Please enter a name for your blocklist');
            return;
        }

        // Parse domains
        const domains = domainsText
            .split('\n')
            .map(d => d.trim())
            .filter(d => d && !d.startsWith('#'));

        if (domains.length === 0) {
            alert('Please enter at least one domain');
            return;
        }

        // Create custom blocklist
        const id = `custom-${Date.now()}`;
        const customList = {
            id,
            name,
            description,
            domains
        };

        this.customBlocklists.push(customList);
        this.blocklistDomains[id] = domains;
        this.state.blocklists.push(id);

        // Re-render blocklists
        this.renderBlocklists();

        // Hide form
        const form = document.querySelector('.custom-blocklist-form');
        if (form) {
            form.classList.remove('active');
            form.querySelector('#customListName').value = '';
            form.querySelector('#customListDescription').value = '';
            form.querySelector('#customListDomains').value = '';
        }
    }

    deleteCustomBlocklist(listId) {
        if (!confirm('Are you sure you want to delete this custom blocklist?')) {
            return;
        }

        // Remove from arrays
        this.customBlocklists = this.customBlocklists.filter(c => c.id !== listId);
        this.state.blocklists = this.state.blocklists.filter(b => b !== listId);
        delete this.blocklistDomains[listId];
        delete this.blocklistExclusions[listId];
        delete this.blocklistAdditions[listId];

        // Re-render
        this.renderBlocklists();
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
            // Collect selected blocklists from expandable cards
            this.updateBlocklistState();

            // Store customizations in state for backend
            this.state.blocklist_exclusions = this.blocklistExclusions;
            this.state.blocklist_additions = this.blocklistAdditions;
            this.state.custom_blocklists = this.customBlocklists;
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
            this.updateUI('forward');

            // Load config preview on review step
            if (this.currentStep === 7) {
                await this.loadConfigPreview();
            }
        }
    }

    prevStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.updateUI('back');
        }
    }

    goToStep(step) {
        this.collectFormData();
        const direction = step > this.currentStep ? 'forward' : 'back';
        this.currentStep = step;
        this.updateUI(direction);

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

        // Build blocklist summary
        let blocklistSummary = '';
        if (this.state.blocklists.length > 0) {
            const listNames = this.state.blocklists.map(id => {
                const def = this.blocklistDefinitions[id];
                if (def) return def.name;
                const custom = this.customBlocklists.find(c => c.id === id);
                if (custom) return `${custom.name} (custom)`;
                return id;
            });
            blocklistSummary = listNames.join(', ');

            // Count customizations
            let totalExclusions = 0;
            let totalAdditions = 0;
            for (const listId of this.state.blocklists) {
                totalExclusions += (this.blocklistExclusions[listId] || []).length;
                totalAdditions += (this.blocklistAdditions[listId] || []).length;
            }
            if (totalExclusions > 0 || totalAdditions > 0) {
                const mods = [];
                if (totalAdditions > 0) mods.push(`+${totalAdditions} added`);
                if (totalExclusions > 0) mods.push(`-${totalExclusions} excluded`);
                blocklistSummary += ` (${mods.join(', ')})`;
            }
        } else {
            blocklistSummary = 'Default only';
        }

        const rows = [
            ['Deployment', this.state.deployment === 'docker' ? 'Docker' : 'Bare Metal'],
            ['Pi-hole IP', this.state.pihole_ip || 'Not set'],
            ['DNS Resolver', this.state.enable_unbound ? 'Unbound (Recursive)' : this.state.upstream_dns],
            ['IPv6', this.state.ipv6 ? 'Enabled' : 'Disabled'],
            ['Blocklists', blocklistSummary],
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

    async copyToClipboard(text, button) {
        try {
            await navigator.clipboard.writeText(text);

            // Show success state
            const copyIcon = button.querySelector('.copy-icon') || button.querySelector('#copyIcon');
            const checkIcon = button.querySelector('.check-icon') || button.querySelector('#copyCheckIcon');
            const copyText = button.querySelector('.copy-text') || button.querySelector('#copyConfigText');

            button.classList.add('copied');
            if (copyIcon) copyIcon.style.display = 'none';
            if (checkIcon) checkIcon.style.display = 'block';
            if (copyText) copyText.textContent = 'Copied!';

            // Reset after 2 seconds
            setTimeout(() => {
                button.classList.remove('copied');
                if (copyIcon) copyIcon.style.display = 'block';
                if (checkIcon) checkIcon.style.display = 'none';
                if (copyText) copyText.textContent = 'Copy';
            }, 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
            alert('Failed to copy to clipboard');
        }
    }

    copyConfig() {
        const code = document.getElementById('configPreview').querySelector('code');
        const text = code.textContent;
        this.copyToClipboard(text, document.getElementById('copyConfigBtn'));
    }

    copyCommands() {
        const code = document.getElementById('commandsPreview').querySelector('code');
        const text = code.textContent;
        this.copyToClipboard(text, document.getElementById('copyCommandsBtn'));
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
        const progressEl = document.getElementById('installProgress');
        progressEl.style.display = 'block';
        progressEl.classList.add('active');
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
        const progressEl = document.getElementById('installProgress');
        progressEl.style.display = 'none';
        progressEl.classList.remove('active');
        document.querySelector(`.step-content[data-step="7"]`).classList.add('active');
        // Footer stays hidden on review page
    }

    showSuccessScreen() {
        const progressEl = document.getElementById('installProgress');
        progressEl.style.display = 'none';
        progressEl.classList.remove('active');
        const successEl = document.getElementById('successScreen');
        successEl.style.display = 'block';
        successEl.classList.add('active');

        const dashboardLink = document.getElementById('dashboardLink');
        dashboardLink.href = `http://${this.state.pihole_ip}/admin`;
        dashboardLink.textContent = `http://${this.state.pihole_ip}/admin`;

        // Trigger confetti
        this.launchConfetti();
    }

    launchConfetti() {
        const canvas = document.getElementById('confettiCanvas');
        const ctx = canvas.getContext('2d');

        // Set canvas size
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const confettiColors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
        const confettiCount = 150;
        const confetti = [];

        // Create confetti particles
        for (let i = 0; i < confettiCount; i++) {
            confetti.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height - canvas.height,
                w: Math.random() * 10 + 5,
                h: Math.random() * 6 + 3,
                color: confettiColors[Math.floor(Math.random() * confettiColors.length)],
                speed: Math.random() * 3 + 2,
                angle: Math.random() * 360,
                spin: (Math.random() - 0.5) * 10,
                drift: (Math.random() - 0.5) * 2,
            });
        }

        let animationFrame;
        const animate = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            let activeConfetti = 0;
            confetti.forEach(c => {
                if (c.y < canvas.height + 20) {
                    activeConfetti++;
                    c.y += c.speed;
                    c.x += c.drift;
                    c.angle += c.spin;

                    ctx.save();
                    ctx.translate(c.x, c.y);
                    ctx.rotate(c.angle * Math.PI / 180);
                    ctx.fillStyle = c.color;
                    ctx.fillRect(-c.w / 2, -c.h / 2, c.w, c.h);
                    ctx.restore();
                }
            });

            if (activeConfetti > 0) {
                animationFrame = requestAnimationFrame(animate);
            } else {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
        };

        animate();

        // Clean up after 5 seconds
        setTimeout(() => {
            cancelAnimationFrame(animationFrame);
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }, 5000);
    }

    // Export/Import functionality
    async exportConfig() {
        this.setButtonLoading('exportBtn', true);
        try {
            // Collect current form data first
            this.collectFormData();
            await this.saveState();

            const exportData = await API.exportConfig();

            // Download as JSON file
            const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'pihole-wizard-config.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            alert('Configuration exported successfully!');
        } catch (e) {
            alert('Export failed: ' + e.message);
        } finally {
            this.setButtonLoading('exportBtn', false);
        }
    }

    async importConfig(event) {
        const file = event.target.files[0];
        if (!file) return;

        this.showLoading('Importing configuration...');
        try {
            const text = await file.text();
            const configData = JSON.parse(text);

            const result = await API.importConfig(configData);

            // Update local state
            this.state = { ...this.state, ...result.state };

            // Update form fields
            this.populateFormFromState();

            // Reset file input
            event.target.value = '';

            this.hideLoading();
            alert('Configuration imported successfully!' +
                  (configData._note ? '\n\nNote: ' + configData._note : ''));

            // Go to step 1 to review
            this.currentStep = 1;
            this.updateUI();
        } catch (e) {
            this.hideLoading();
            alert('Import failed: ' + e.message);
            event.target.value = '';
        }
    }

    populateFormFromState() {
        // Deployment
        const deploymentInput = document.querySelector(`input[name="deployment"][value="${this.state.deployment}"]`);
        if (deploymentInput) {
            deploymentInput.checked = true;
            this.updateOptionCards();
        }

        // Network
        if (this.state.pihole_ip) {
            document.getElementById('piholeIp').value = this.state.pihole_ip;
        }
        if (this.state.network_interface) {
            document.getElementById('networkInterface').value = this.state.network_interface;
        }

        // DNS
        document.getElementById('enableUnbound').checked = this.state.enable_unbound;
        document.getElementById('ipv6').checked = this.state.ipv6;
        if (this.state.upstream_dns) {
            document.getElementById('upstreamDnsSelect').value = this.state.upstream_dns;
        }
        if (this.state.custom_dns) {
            document.getElementById('customDnsInput').value = this.state.custom_dns;
        }

        // DHCP
        document.getElementById('dhcpEnabled').checked = this.state.dhcp_enabled;
        if (this.state.dhcp_start) {
            document.getElementById('dhcpStart').value = this.state.dhcp_start;
        }
        if (this.state.dhcp_end) {
            document.getElementById('dhcpEnd').value = this.state.dhcp_end;
        }
        if (this.state.dhcp_router) {
            document.getElementById('dhcpRouter').value = this.state.dhcp_router;
        }

        // Restore blocklist customizations
        if (this.state.blocklist_exclusions) {
            this.blocklistExclusions = this.state.blocklist_exclusions;
        }
        if (this.state.blocklist_additions) {
            this.blocklistAdditions = this.state.blocklist_additions;
        }
        if (this.state.custom_blocklists) {
            this.customBlocklists = this.state.custom_blocklists;
        }

        // Re-render blocklists with state
        this.renderBlocklists();

        // Update UI states
        this.updateDeploymentUI();
        this.updateDnsUI();
        this.updateDhcpUI();
    }

    // Update functionality
    openUpdateModal() {
        document.getElementById('updateModal').style.display = 'block';
        document.getElementById('modalOverlay').style.display = 'block';
        // Reset modal state
        document.getElementById('updateCheck').style.display = 'block';
        document.getElementById('updateStatus').style.display = 'none';
        document.getElementById('updateProgressContainer').style.display = 'none';
    }

    closeUpdateModal() {
        document.getElementById('updateModal').style.display = 'none';
        document.getElementById('modalOverlay').style.display = 'none';
    }

    async checkForUpdates() {
        const checkBtn = document.getElementById('checkUpdateBtn');
        checkBtn.disabled = true;
        checkBtn.textContent = 'Checking...';

        try {
            const result = await API.checkForUpdates();

            document.getElementById('updateCheck').style.display = 'none';
            document.getElementById('updateStatus').style.display = 'block';

            const infoEl = document.getElementById('updateInfo');

            if (result.has_existing_install) {
                infoEl.innerHTML = `
                    <p><strong class="status-pass">Pi-hole installation found!</strong></p>
                    ${result.install_path ? `<p>Location: <code>${result.install_path}</code></p>` : ''}
                    ${result.current_version ? `<p>Current version: ${result.current_version}</p>` : ''}
                    ${result.running_containers?.length ? `<p>Running containers: ${result.running_containers.join(', ')}</p>` : ''}
                    <p>${result.message}</p>
                `;
                document.getElementById('startUpdateBtn').style.display = 'inline-flex';
            } else {
                infoEl.innerHTML = `
                    <p><strong class="status-fail">No installation found</strong></p>
                    <p>${result.message}</p>
                `;
                document.getElementById('startUpdateBtn').style.display = 'none';
            }
        } catch (e) {
            alert('Check failed: ' + e.message);
        } finally {
            checkBtn.disabled = false;
            checkBtn.textContent = 'Check for Updates';
        }
    }

    async startUpdate() {
        const startBtn = document.getElementById('startUpdateBtn');
        startBtn.disabled = true;
        startBtn.textContent = 'Updating...';

        document.getElementById('updateProgressContainer').style.display = 'block';

        try {
            await API.startUpdate();

            // Poll for status
            const statusInterval = setInterval(async () => {
                try {
                    const status = await API.getUpdateStatus();

                    document.getElementById('updateProgressBar').style.width = `${status.progress}%`;
                    document.getElementById('updateStep').textContent = status.current_step;

                    if (status.status === 'success') {
                        clearInterval(statusInterval);
                        document.getElementById('updateInfo').innerHTML = `
                            <p><strong class="status-pass">Update complete!</strong></p>
                            <p>${status.message}</p>
                        `;
                        startBtn.style.display = 'none';
                    } else if (status.status === 'failed') {
                        clearInterval(statusInterval);
                        document.getElementById('updateInfo').innerHTML = `
                            <p><strong class="status-fail">Update failed</strong></p>
                            <p>${status.message}</p>
                        `;
                        startBtn.disabled = false;
                        startBtn.textContent = 'Retry Update';
                    }
                } catch (e) {
                    clearInterval(statusInterval);
                }
            }, 1000);
        } catch (e) {
            alert('Update failed to start: ' + e.message);
            startBtn.disabled = false;
            startBtn.textContent = 'Update Now';
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new WizardApp();
});
