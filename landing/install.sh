#!/bin/bash
#
# Pi-hole Wizard Installer
# This script installs Docker (if needed) and runs the Pi-hole Wizard web app
#
# Usage: curl -sSL https://pihole-wizard.com/install.sh | bash
# Uninstall: curl -sSL https://pihole-wizard.com/install.sh | bash -s -- --uninstall
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Uninstall function
uninstall() {
    echo ""
    echo -e "${YELLOW}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║       Pi-hole Wizard Uninstaller          ║${NC}"
    echo -e "${YELLOW}╚═══════════════════════════════════════════╝${NC}"
    echo ""

    INSTALL_DIR="$HOME/pihole-wizard"

    if [ ! -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}Pi-hole Wizard installation not found at $INSTALL_DIR${NC}"
        exit 0
    fi

    echo -e "${YELLOW}This will remove:${NC}"
    echo -e "  • Pi-hole Wizard container"
    echo -e "  • Pi-hole Wizard Docker image"
    echo -e "  • Installation directory ($INSTALL_DIR)"
    echo ""
    echo -e "${BLUE}Note:${NC} This will NOT remove Pi-hole itself or Docker."
    echo ""

    # Check for TTY
    if [ -t 0 ] || [ -e /dev/tty ]; then
        exec 3</dev/tty
        read -p "Are you sure you want to uninstall? [y/N]: " -n 1 -r REPLY <&3
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${BLUE}Uninstall cancelled.${NC}"
            exit 0
        fi
    fi

    echo ""
    echo -e "${YELLOW}→${NC} Stopping Pi-hole Wizard..."
    cd "$INSTALL_DIR" 2>/dev/null && {
        docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true
    }

    echo -e "${YELLOW}→${NC} Removing Docker container..."
    docker rm -f pihole-wizard 2>/dev/null || true

    echo -e "${YELLOW}→${NC} Removing Docker image..."
    docker rmi ghcr.io/anishj9/pihole-wizard:latest 2>/dev/null || true

    echo -e "${YELLOW}→${NC} Removing installation directory..."
    rm -rf "$INSTALL_DIR"

    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Pi-hole Wizard has been uninstalled.${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Thanks for trying Pi-hole Wizard!"
    echo -e "  If you have feedback, visit: ${BLUE}https://github.com/AnishJ9/pihole-wizard-web${NC}"
    echo ""
    exit 0
}

# Check for uninstall flag
if [ "$1" = "--uninstall" ] || [ "$1" = "-u" ] || [ "$1" = "uninstall" ]; then
    uninstall
fi

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
        # Redirect stdin from terminal for all subsequent reads
        exec 3</dev/tty

        echo -e "What would you like to do?"
        echo ""
        echo -e "  ${GREEN}1)${NC} Connect to my Raspberry Pi now (SSH)"
        echo -e "  ${GREEN}2)${NC} Continue anyway (I know what I'm doing)"
        echo -e "  ${GREEN}3)${NC} Exit"
        echo ""
        read -p "Choose [1/2/3]: " -n 1 -r REPLY <&3
        echo ""

        case $REPLY in
            1)
                echo ""
                echo -e "${BLUE}Let's connect to your Raspberry Pi!${NC}"
                echo ""
                echo -e "${YELLOW}Note:${NC} Make sure this computer is on the same Wi-Fi/network as your Pi."
                echo ""

                # Try to find Raspberry Pi on the network
                echo -e "${YELLOW}Scanning your network for Raspberry Pi devices...${NC}"
                echo ""

                FOUND_PIS=""

                # Get local network range
                if command -v ip &> /dev/null; then
                    LOCAL_IP=$(ip route get 1 2>/dev/null | awk '{print $7}' | head -1)
                elif command -v ifconfig &> /dev/null; then
                    LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
                fi

                if [ -n "$LOCAL_IP" ]; then
                    # Extract network prefix (e.g., 192.168.1)
                    NET_PREFIX=$(echo $LOCAL_IP | cut -d. -f1-3)

                    # Method 1: Check ARP table for known Pi MAC addresses (Raspberry Pi Foundation OUIs)
                    # Pi MACs start with: b8:27:eb, dc:a6:32, e4:5f:01, d8:3a:dd
                    if command -v arp &> /dev/null; then
                        FOUND_PIS=$(arp -a 2>/dev/null | grep -iE "b8:27:eb|dc:a6:32|e4:5f:01|d8:3a:dd|raspberry" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | head -5)
                    fi

                    # Method 2: If arp didn't find anything, try pinging common Pi hostnames
                    if [ -z "$FOUND_PIS" ]; then
                        for hostname in raspberrypi raspberry pi pihole; do
                            PI_IP_FOUND=$(ping -c 1 -W 1 $hostname 2>/dev/null | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | head -1)
                            if [ -n "$PI_IP_FOUND" ]; then
                                FOUND_PIS="$PI_IP_FOUND"
                                break
                            fi
                        done
                    fi

                    # Method 3: Quick scan of common IPs (only if we found nothing)
                    if [ -z "$FOUND_PIS" ] && command -v ping &> /dev/null; then
                        echo -e "${YELLOW}Checking common IP addresses...${NC}"
                        for i in 1 2 100 101 102 50 51 150 200; do
                            TEST_IP="${NET_PREFIX}.${i}"
                            if ping -c 1 -W 1 "$TEST_IP" &>/dev/null; then
                                # Check if SSH port is open (likely a Pi or server)
                                if nc -z -w 1 "$TEST_IP" 22 2>/dev/null || \
                                   (echo >/dev/tcp/$TEST_IP/22) 2>/dev/null; then
                                    FOUND_PIS="${FOUND_PIS}${TEST_IP}\n"
                                fi
                            fi
                        done
                    fi
                fi

                # Show results
                if [ -n "$FOUND_PIS" ]; then
                    echo -e "${GREEN}Found possible Raspberry Pi device(s):${NC}"
                    echo ""
                    COUNT=1
                    echo "$FOUND_PIS" | while read -r ip; do
                        if [ -n "$ip" ]; then
                            echo -e "  ${GREEN}$COUNT)${NC} $ip"
                            COUNT=$((COUNT + 1))
                        fi
                    done
                    echo ""
                    echo -e "  ${GREEN}m)${NC} Enter IP manually"
                    echo ""
                    read -p "Choose an option: " PI_CHOICE <&3

                    if [ "$PI_CHOICE" = "m" ] || [ "$PI_CHOICE" = "M" ]; then
                        read -p "Enter your Pi's IP address: " PI_IP <&3
                    else
                        PI_IP=$(echo "$FOUND_PIS" | sed -n "${PI_CHOICE}p")
                    fi
                else
                    echo -e "${YELLOW}Couldn't auto-detect your Pi.${NC}"
                    echo ""
                    echo -e "Your Pi's IP is usually something like: ${BLUE}${NET_PREFIX}.X${NC}"
                    echo ""
                    echo -e "To find it, you can:"
                    echo -e "  • Check your router's admin page for connected devices"
                    echo -e "  • Look at your Pi's screen (if connected) - run ${BLUE}hostname -I${NC}"
                    echo -e "  • Use a network scanner app on your phone"
                    echo ""
                    read -p "Enter your Pi's IP address: " PI_IP <&3
                fi

                if [ -z "$PI_IP" ]; then
                    echo -e "${RED}No IP address entered. Exiting.${NC}"
                    exit 1
                fi
                read -p "Enter username (default: pi): " PI_USER <&3
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

# Check if port is available
check_port() {
    local port=$1
    if command -v lsof &> /dev/null; then
        if lsof -i :$port &> /dev/null; then
            return 1
        fi
    elif command -v netstat &> /dev/null; then
        if netstat -tuln | grep -q ":$port "; then
            return 1
        fi
    elif command -v ss &> /dev/null; then
        if ss -tuln | grep -q ":$port "; then
            return 1
        fi
    fi
    return 0
}

# Cleanup on failure
cleanup_failed_install() {
    echo ""
    echo -e "${YELLOW}→${NC} Cleaning up failed installation..."
    cd "$HOME" 2>/dev/null
    docker rm -f pihole-wizard 2>/dev/null || true
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
    fi
    echo -e "${GREEN}✓${NC} Cleanup complete"
}

# Error handler with retry option
handle_error() {
    local error_msg="$1"
    local retry_func="$2"

    echo ""
    echo -e "${RED}══════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  Error: ${error_msg}${NC}"
    echo -e "${RED}══════════════════════════════════════════════════════════${NC}"
    echo ""

    if [ -t 0 ] || [ -e /dev/tty ]; then
        exec 3</dev/tty 2>/dev/null || exec 3<&0
        echo -e "What would you like to do?"
        echo ""
        echo -e "  ${GREEN}1)${NC} Retry"
        echo -e "  ${GREEN}2)${NC} Clean up and exit"
        echo -e "  ${GREEN}3)${NC} Exit (keep partial install)"
        echo ""
        read -p "Choose [1/2/3]: " -n 1 -r REPLY <&3 2>/dev/null || REPLY="2"
        echo ""

        case $REPLY in
            1)
                echo -e "${YELLOW}Retrying...${NC}"
                return 0  # Signal to retry
                ;;
            2)
                cleanup_failed_install
                exit 1
                ;;
            *)
                echo -e "${YELLOW}Exiting. You may have a partial installation at $INSTALL_DIR${NC}"
                exit 1
                ;;
        esac
    else
        cleanup_failed_install
        exit 1
    fi
}

# Main installation
main() {
    INSTALL_DIR="$HOME/pihole-wizard"

    # Check/install Docker
    if ! check_docker; then
        echo -e "${YELLOW}Docker not found. Installing...${NC}"
        if ! install_docker; then
            handle_error "Failed to install Docker" || main
            return
        fi

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
        handle_error "Docker Compose not found. Please install Docker Compose and try again." || main
        return
    fi

    # Check if port 8080 is available
    echo -e "${YELLOW}→${NC} Checking port availability..."
    if ! check_port 8080; then
        echo -e "${YELLOW}!${NC} Port 8080 is already in use."
        echo ""
        echo -e "  This could be:"
        echo -e "  • Pi-hole Wizard already running"
        echo -e "  • Another web service"
        echo ""

        # Check if it's already our container
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "pihole-wizard"; then
            echo -e "${GREEN}✓${NC} Pi-hole Wizard is already running!"
            LOCAL_IP=$(get_local_ip)
            echo ""
            echo -e "  Access it at: ${BLUE}http://${LOCAL_IP}:8080${NC}"
            echo ""
            exit 0
        fi

        if [ -t 0 ] || [ -e /dev/tty ]; then
            exec 3</dev/tty 2>/dev/null || exec 3<&0
            echo -e "What would you like to do?"
            echo ""
            echo -e "  ${GREEN}1)${NC} Stop whatever is using port 8080 and continue"
            echo -e "  ${GREEN}2)${NC} Exit"
            echo ""
            read -p "Choose [1/2]: " -n 1 -r REPLY <&3 2>/dev/null || REPLY="2"
            echo ""

            if [ "$REPLY" = "1" ]; then
                echo -e "${YELLOW}→${NC} Attempting to free port 8080..."
                $SUDO lsof -ti :8080 | xargs -r $SUDO kill -9 2>/dev/null || true
                sleep 2
                if ! check_port 8080; then
                    echo -e "${RED}Could not free port 8080. Please manually stop the service using it.${NC}"
                    exit 1
                fi
                echo -e "${GREEN}✓${NC} Port 8080 is now available"
            else
                exit 0
            fi
        else
            echo -e "${RED}Port 8080 is in use. Please free it and try again.${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✓${NC} Port 8080 is available"
    fi

    # Check internet connectivity
    echo -e "${YELLOW}→${NC} Checking internet connection..."
    if ! curl -s --connect-timeout 5 https://ghcr.io > /dev/null 2>&1; then
        if ! ping -c 1 -W 5 8.8.8.8 > /dev/null 2>&1; then
            handle_error "No internet connection. Please check your network and try again." || main
            return
        fi
    fi
    echo -e "${GREEN}✓${NC} Internet connection OK"

    # Create installation directory
    echo -e "${YELLOW}→${NC} Creating installation directory: $INSTALL_DIR"
    if ! mkdir -p "$INSTALL_DIR"; then
        handle_error "Could not create directory $INSTALL_DIR" || main
        return
    fi
    cd "$INSTALL_DIR"

    # Download docker-compose.yml
    echo -e "${YELLOW}→${NC} Configuring Pi-hole Wizard..."

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

    # Pull the image with retry logic
    echo -e "${YELLOW}→${NC} Pulling Docker image (this may take a few minutes)..."

    PULL_SUCCESS=false
    for attempt in 1 2 3; do
        if docker compose pull 2>/dev/null || docker-compose pull 2>/dev/null; then
            PULL_SUCCESS=true
            break
        fi
        if [ $attempt -lt 3 ]; then
            echo -e "${YELLOW}!${NC} Pull failed. Retrying in 5 seconds... (attempt $attempt/3)"
            sleep 5
        fi
    done

    if [ "$PULL_SUCCESS" = true ]; then
        echo -e "${GREEN}✓${NC} Image downloaded"
    else
        echo -e "${YELLOW}!${NC} Could not pull image. Trying to build locally..."
        # Clone and build
        if command -v git &> /dev/null; then
            rm -rf docker-compose.yml
            if ! git clone https://github.com/AnishJ9/pihole-wizard-web.git . 2>/dev/null; then
                handle_error "Failed to download Pi-hole Wizard. Check your internet connection." || main
                return
            fi
            if ! (docker compose build 2>/dev/null || docker-compose build); then
                handle_error "Failed to build Pi-hole Wizard image." || main
                return
            fi
        else
            handle_error "Git not installed. Please install git and try again." || main
            return
        fi
    fi

    # Start the wizard
    echo -e "${YELLOW}→${NC} Starting Pi-hole Wizard..."
    if ! (docker compose up -d 2>/dev/null || docker-compose up -d); then
        handle_error "Failed to start Pi-hole Wizard container." || main
        return
    fi

    # Wait for startup and verify it's running
    echo -e "${YELLOW}→${NC} Waiting for wizard to start..."
    sleep 3

    # Verify container is running
    if ! docker ps --format '{{.Names}}' | grep -q "pihole-wizard"; then
        echo -e "${YELLOW}!${NC} Container may have failed to start. Checking logs..."
        docker logs pihole-wizard 2>&1 | tail -10
        handle_error "Pi-hole Wizard container failed to start." || main
        return
    fi

    # Verify the service is responding
    LOCAL_IP=$(get_local_ip)
    echo -e "${YELLOW}→${NC} Verifying service is responding..."

    SERVICE_UP=false
    for i in 1 2 3 4 5; do
        if curl -s --connect-timeout 2 "http://localhost:8080/health" > /dev/null 2>&1 || \
           curl -s --connect-timeout 2 "http://localhost:8080" > /dev/null 2>&1; then
            SERVICE_UP=true
            break
        fi
        sleep 2
    done

    if [ "$SERVICE_UP" = false ]; then
        echo -e "${YELLOW}!${NC} Service may still be starting. Check http://${LOCAL_IP}:8080 in a moment."
    else
        echo -e "${GREEN}✓${NC} Service is responding"
    fi

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
    echo -e "  To stop the wizard:    ${GREEN}cd $INSTALL_DIR && docker compose down${NC}"
    echo -e "  To uninstall:          ${GREEN}curl -sSL pihole-wizard.com/install.sh | bash -s -- --uninstall${NC}"
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
