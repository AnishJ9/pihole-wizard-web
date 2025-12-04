#!/bin/bash
#
# Pi-hole Wizard Installer
# This script installs Docker (if needed) and runs the Pi-hole Wizard web app
#
# Usage: curl -sSL https://pihole-wizard.com/install.sh | bash
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Pi-hole Wizard Installer            ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
echo ""

# Detect if running on a Raspberry Pi or compatible device
detect_device() {
    # Check for Raspberry Pi
    if [ -f /proc/device-tree/model ]; then
        MODEL=$(cat /proc/device-tree/model 2>/dev/null)
        if echo "$MODEL" | grep -qi "raspberry"; then
            echo -e "${GREEN}✓${NC} Detected: $MODEL"
            return 0
        fi
    fi

    # Check for Debian/Ubuntu on ARM (likely a Pi or similar SBC)
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        ARCH=$(uname -m)
        if [[ "$ARCH" == "aarch64" || "$ARCH" == "armv7l" || "$ARCH" == "armhf" ]]; then
            echo -e "${GREEN}✓${NC} Detected: $PRETTY_NAME on $ARCH (ARM device)"
            return 0
        fi
    fi

    # Not a Pi or ARM device - warn the user
    return 1
}

# Check if this is the right device
if ! detect_device; then
    OS_NAME=$(uname -s)
    echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ⚠️  Wait! This doesn't look like a Raspberry Pi              ║${NC}"
    echo -e "${YELLOW}╠═══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${YELLOW}║                                                               ║${NC}"
    echo -e "${YELLOW}║  You're running this on: ${NC}$(printf '%-35s' "$OS_NAME ($(uname -m))")${YELLOW}║${NC}"
    echo -e "${YELLOW}║                                                               ║${NC}"
    echo -e "${YELLOW}║  Pi-hole Wizard is designed to run on your Raspberry Pi,     ║${NC}"
    echo -e "${YELLOW}║  not your personal computer.                                  ║${NC}"
    echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    # Check if we have a terminal for interactive input
    if [ -t 0 ] || [ -e /dev/tty ]; then
        exec < /dev/tty

        echo -e "What would you like to do?"
        echo ""
        echo -e "  ${GREEN}1)${NC} Connect to my Raspberry Pi now (SSH)"
        echo -e "  ${GREEN}2)${NC} Continue anyway (I know what I'm doing)"
        echo -e "  ${GREEN}3)${NC} Exit"
        echo ""
        read -p "Choose [1/2/3]: " -n 1 -r REPLY
        echo ""

        case $REPLY in
            1)
                echo ""
                echo -e "${BLUE}Let's connect to your Raspberry Pi!${NC}"
                echo ""
                read -p "Enter your Pi's IP address (e.g., 192.168.1.100): " PI_IP
                if [ -z "$PI_IP" ]; then
                    echo -e "${RED}No IP address entered. Exiting.${NC}"
                    exit 1
                fi
                read -p "Enter username (default: pi): " PI_USER
                PI_USER=${PI_USER:-pi}
                echo ""
                echo -e "${YELLOW}Connecting to ${PI_USER}@${PI_IP}...${NC}"
                echo -e "${YELLOW}Once connected, the installer will run automatically.${NC}"
                echo ""
                # SSH into Pi and run the installer there
                ssh -t "${PI_USER}@${PI_IP}" "curl -sSL https://pihole-wizard.com/install.sh | bash"
                exit $?
                ;;
            2)
                echo ""
                echo -e "${YELLOW}Continuing on this device...${NC}"
                echo ""
                ;;
            *)
                echo ""
                echo -e "${BLUE}No problem! Run this on your Raspberry Pi when you're ready.${NC}"
                exit 0
                ;;
        esac
    else
        # No terminal available, just exit with instructions
        echo ""
        echo -e "To connect to your Pi, run:"
        echo -e "  ${GREEN}ssh pi@<your-pi-ip>${NC}"
        echo -e "Then run the installer there."
        echo ""
        exit 0
    fi
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        DOCKER_ARCH="amd64"
        ;;
    aarch64|arm64)
        DOCKER_ARCH="arm64"
        ;;
    armv7l|armhf)
        DOCKER_ARCH="armhf"
        ;;
    *)
        echo -e "${RED}Unsupported architecture: $ARCH${NC}"
        exit 1
        ;;
esac

echo -e "${GREEN}✓${NC} Detected architecture: $ARCH"

# Check for Docker
check_docker() {
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}✓${NC} Docker is installed"
        return 0
    else
        return 1
    fi
}

# Install Docker
install_docker() {
    echo -e "${YELLOW}→${NC} Installing Docker..."

    # Use the official Docker install script
    curl -fsSL https://get.docker.com | $SUDO sh

    # Add current user to docker group
    if [ "$EUID" -ne 0 ]; then
        $SUDO usermod -aG docker $USER
        echo -e "${YELLOW}!${NC} Added $USER to docker group. You may need to log out and back in."
    fi

    # Start Docker service
    $SUDO systemctl enable docker
    $SUDO systemctl start docker

    echo -e "${GREEN}✓${NC} Docker installed successfully"
}

# Check for Docker Compose
check_docker_compose() {
    if docker compose version &> /dev/null; then
        echo -e "${GREEN}✓${NC} Docker Compose is available"
        return 0
    elif command -v docker-compose &> /dev/null; then
        echo -e "${GREEN}✓${NC} Docker Compose (legacy) is available"
        return 0
    else
        return 1
    fi
}

# Get local IP address
get_local_ip() {
    # Try multiple methods to get IP
    IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$IP" ]; then
        IP=$(ip route get 1 2>/dev/null | awk '{print $7}' | head -1)
    fi
    if [ -z "$IP" ]; then
        IP="localhost"
    fi
    echo $IP
}

# Main installation
main() {
    # Check/install Docker
    if ! check_docker; then
        echo -e "${YELLOW}Docker not found. Installing...${NC}"
        install_docker

        # If we can't run docker without sudo, we need to use newgrp or re-login
        if ! docker info &> /dev/null; then
            echo ""
            echo -e "${YELLOW}══════════════════════════════════════════════════════════${NC}"
            echo -e "${YELLOW}  Docker was installed but requires a new login session.${NC}"
            echo -e "${YELLOW}  Please run: ${NC}${GREEN}newgrp docker${NC}${YELLOW} and then re-run this script.${NC}"
            echo -e "${YELLOW}  Or log out and log back in, then run:${NC}"
            echo -e "${GREEN}  curl -sSL https://pihole-wizard.com/install.sh | bash${NC}"
            echo -e "${YELLOW}══════════════════════════════════════════════════════════${NC}"
            exit 0
        fi
    fi

    # Check Docker Compose
    if ! check_docker_compose; then
        echo -e "${RED}Docker Compose not found and couldn't be installed.${NC}"
        exit 1
    fi

    # Create installation directory
    INSTALL_DIR="$HOME/pihole-wizard"
    echo -e "${YELLOW}→${NC} Creating installation directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"

    # Download docker-compose.yml
    echo -e "${YELLOW}→${NC} Downloading Pi-hole Wizard..."

    cat > docker-compose.yml << 'EOF'
# Pi-hole Wizard Web
# Generated by install.sh

services:
  pihole-wizard:
    image: ghcr.io/anishj9/pihole-wizard:latest
    container_name: pihole-wizard
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./output:/app/output
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
    restart: unless-stopped
EOF

    # For local development/testing, build from source instead
    # Uncomment below if you want to build locally:
    # git clone https://github.com/AnishJ9/pihole-wizard-web.git .
    # docker compose build

    # Pull the image
    echo -e "${YELLOW}→${NC} Pulling Docker image (this may take a few minutes)..."
    if docker compose pull 2>/dev/null || docker-compose pull 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Image downloaded"
    else
        echo -e "${YELLOW}!${NC} Could not pull image. Trying to build locally..."
        # Clone and build
        if command -v git &> /dev/null; then
            rm -rf docker-compose.yml
            git clone https://github.com/AnishJ9/pihole-wizard-web.git .
            docker compose build 2>/dev/null || docker-compose build
        else
            echo -e "${RED}Git not installed. Please install git and try again.${NC}"
            exit 1
        fi
    fi

    # Start the wizard
    echo -e "${YELLOW}→${NC} Starting Pi-hole Wizard..."
    docker compose up -d 2>/dev/null || docker-compose up -d

    # Wait for startup
    echo -e "${YELLOW}→${NC} Waiting for wizard to start..."
    sleep 3

    # Get the IP
    LOCAL_IP=$(get_local_ip)

    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Pi-hole Wizard is running!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Open this URL in your browser:"
    echo ""
    echo -e "  ${BLUE}http://${LOCAL_IP}:8080${NC}"
    echo ""
    echo -e "  Or if you're on the same device:"
    echo -e "  ${BLUE}http://localhost:8080${NC}"
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${YELLOW}Tip:${NC} You can open this URL on your phone, tablet,"
    echo -e "  or any device connected to your network."
    echo ""
    echo -e "  To stop the wizard later: ${GREEN}cd $INSTALL_DIR && docker compose down${NC}"
    echo ""

    # Try to open browser (works on desktop Linux, ignored on headless)
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://${LOCAL_IP}:8080" 2>/dev/null &
    elif command -v open &> /dev/null; then
        open "http://${LOCAL_IP}:8080" 2>/dev/null &
    fi
}

# Run main function
main
