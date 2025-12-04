# Pi-hole Wizard Web

A user-friendly web application that guides you through setting up Pi-hole and Unbound on your network.

**No technical knowledge required** - just run one command and follow the visual wizard.

## How Users Find and Use This

### The User Journey

1. **User visits your landing page** (`pihole-wizard.com`)
2. **Copies the one-liner install command**
3. **Runs it on their Raspberry Pi** (via SSH or terminal)
4. **Opens the wizard URL** in their browser (any device on the network)
5. **Clicks through the wizard** - answers simple questions
6. **Pi-hole is installed!** - donation prompt appears

### Distribution Strategy

You need to host two things:

1. **Landing page** (`landing/index.html`) - Static HTML, host anywhere (GitHub Pages, Netlify, Vercel)
2. **Install script** (`install.sh`) - Host on same domain or GitHub raw URL

The install script automatically:
- Installs Docker if needed
- Downloads and runs the Pi-hole Wizard container
- Displays the URL for the user to open

## Features

- **Step-by-step wizard** - Easy to follow, even for non-technical users
- **Auto-detection** - Automatically detects your network settings
- **Config preview** - See exactly what will be created before installing
- **One-click install** - Deploys Pi-hole with a single click
- **AI troubleshooting** - Get help when things go wrong (optional, requires API key)
- **Works on Raspberry Pi** - ARM-compatible Docker image

## Quick Start

### For End Users (on Raspberry Pi)

```bash
curl -sSL https://pihole-wizard.com/install.sh | bash
```

Then open the displayed URL in any browser.

### For Development

```bash
# Clone the repository
git clone https://github.com/anishjoseph/pihole-wizard-web.git
cd pihole-wizard-web

# Option A: Docker
docker-compose up -d
open http://localhost:8080

# Option B: Run directly
pip install fastapi uvicorn anthropic netifaces pydantic python-multipart
uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

## Deployment Checklist

To launch this for real users:

### 1. Push Docker Image to Registry
```bash
# Build multi-arch image
docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 \
  -t ghcr.io/anishjoseph/pihole-wizard:latest --push .
```

### 2. Host the Landing Page
- Deploy `landing/index.html` to GitHub Pages, Netlify, or Vercel
- Get a domain name (`pihole-wizard.com`)

### 3. Host the Install Script
- Update the URLs in `install.sh` to point to your Docker image
- Host at `https://pihole-wizard.com/install.sh`

### 4. Set Up Donation Links
- Create accounts on Buy Me a Coffee / GitHub Sponsors / Ko-fi
- Update the links in `frontend/index.html` (success screen)
- Update the links in `landing/index.html`

## Usage

1. **Check Prerequisites** - The wizard verifies Docker is installed and ports are available
2. **Choose Deployment** - Docker (recommended) or bare-metal installation
3. **Configure Network** - Enter your Pi-hole's static IP address
4. **Configure DNS** - Enable Unbound for recursive DNS or choose an upstream provider
5. **Configure DHCP** - Optionally use Pi-hole as your DHCP server
6. **Set Password** - Secure the web admin interface
7. **Review & Install** - Preview configs and install with one click

## AI Troubleshooting

The wizard includes an AI chat feature powered by Claude that can help you troubleshoot issues. To use it:

1. Get an API key from [Anthropic](https://console.anthropic.com/)
2. Click "AI Chat" in the header
3. Enter your API key (stored locally in your browser)
4. Ask questions about your Pi-hole setup

## What Gets Installed

After running the wizard, you'll have:

- **Pi-hole** - Network-wide ad blocker
- **Unbound** - Recursive DNS resolver (optional but recommended)
- **Docker containers** - Easy to manage and update

All configuration files are saved to the `output/` directory.

## System Requirements

- Docker and Docker Compose
- 1GB RAM (2GB recommended)
- 4GB disk space
- Network access to pull Docker images

## Supported Platforms

- Linux (x86_64, ARM64)
- macOS (Intel, Apple Silicon)
- Raspberry Pi (3, 4, 5)
- Windows with WSL2

## Security Notes

- The wizard needs access to the Docker socket to install containers
- Your Anthropic API key is stored only in your browser's localStorage
- No data is sent to external servers except AI chat (if enabled)
- All generated configs stay on your local machine

## Troubleshooting

### Port 53 is in use

Another DNS service (like systemd-resolved) may be using port 53. On Ubuntu/Debian:

```bash
sudo systemctl disable systemd-resolved
sudo systemctl stop systemd-resolved
```

### Docker not found

Install Docker using the official script:

```bash
curl -fsSL https://get.docker.com | sh
```

### Permission denied for Docker socket

Add your user to the docker group:

```bash
sudo usermod -aG docker $USER
# Then log out and back in
```

## Support the Project

This tool is **free and open source**. If it saved you time, consider supporting:

- [Buy Me a Coffee](https://buymeacoffee.com)
- [GitHub Sponsors](https://github.com/sponsors)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [Pi-hole](https://pi-hole.net/) - Network ad blocker
- [Unbound](https://nlnetlabs.nl/projects/unbound/) - DNS resolver
- [Claude](https://anthropic.com/) - AI troubleshooting
