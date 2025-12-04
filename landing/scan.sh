#!/bin/bash
#
# Pi-hole Wizard - Raspberry Pi Scanner
# Finds Raspberry Pi devices on your local network
#
# Usage: curl -sSL https://pihole-wizard.com/scan.sh | bash
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Pi-hole Wizard - Pi Scanner           ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Scanning your network for Raspberry Pi devices...${NC}"
echo ""

FOUND_PIS=()

# Method 1: Try mDNS/Bonjour hostnames
echo -e "${YELLOW}→${NC} Checking common hostnames..."
MDNS_HOSTS=("raspberrypi.local" "raspberrypi4.local" "raspberrypi5.local" "pihole.local" "pi.local")

for hostname in "${MDNS_HOSTS[@]}"; do
    # Try to resolve the hostname
    if command -v getent &> /dev/null; then
        ip=$(getent hosts "$hostname" 2>/dev/null | awk '{print $1}')
    elif command -v dscacheutil &> /dev/null; then
        # macOS
        ip=$(dscacheutil -q host -a name "$hostname" 2>/dev/null | grep "ip_address" | awk '{print $2}')
    else
        ip=$(ping -c 1 -W 1 "$hostname" 2>/dev/null | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | head -1)
    fi

    if [ -n "$ip" ]; then
        echo -e "  ${GREEN}✓${NC} Found: $hostname → $ip"
        FOUND_PIS+=("$ip|$hostname|mDNS")
    fi
done

# Method 2: Check ARP table for Raspberry Pi MAC prefixes
echo -e "${YELLOW}→${NC} Checking ARP table for Raspberry Pi devices..."

# Raspberry Pi Foundation MAC prefixes
PI_MAC_PREFIXES=("b8:27:eb" "dc:a6:32" "e4:5f:01" "d8:3a:dd" "2c:cf:67" "28:cd:c1")

if command -v arp &> /dev/null; then
    arp_output=$(arp -a 2>/dev/null)

    for prefix in "${PI_MAC_PREFIXES[@]}"; do
        while IFS= read -r line; do
            if echo "$line" | grep -qi "$prefix"; then
                # Extract IP - handles both Linux and macOS arp output
                ip=$(echo "$line" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | head -1)
                if [ -n "$ip" ]; then
                    # Check if we already found this IP
                    already_found=false
                    for found in "${FOUND_PIS[@]}"; do
                        if [[ "$found" == "$ip|"* ]]; then
                            already_found=true
                            break
                        fi
                    done
                    if [ "$already_found" = false ]; then
                        echo -e "  ${GREEN}✓${NC} Found: $ip (Raspberry Pi MAC address)"
                        FOUND_PIS+=("$ip||ARP")
                    fi
                fi
            fi
        done <<< "$arp_output"
    done
fi

# Method 3: Quick ping sweep to populate ARP table, then recheck
echo -e "${YELLOW}→${NC} Running quick network scan..."

# Get local IP and subnet
if command -v ip &> /dev/null; then
    LOCAL_IP=$(ip route get 1 2>/dev/null | awk '{print $7}' | head -1)
elif command -v ifconfig &> /dev/null; then
    LOCAL_IP=$(ifconfig 2>/dev/null | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
fi

if [ -n "$LOCAL_IP" ]; then
    SUBNET=$(echo "$LOCAL_IP" | cut -d'.' -f1-3)

    # Quick ping sweep (background, just to populate ARP)
    for i in {1..254}; do
        ping -c 1 -W 1 "$SUBNET.$i" &>/dev/null &
    done

    # Wait a moment for pings to complete
    sleep 3

    # Kill any remaining pings
    pkill -f "ping -c 1" 2>/dev/null

    # Recheck ARP table
    if command -v arp &> /dev/null; then
        arp_output=$(arp -a 2>/dev/null)

        for prefix in "${PI_MAC_PREFIXES[@]}"; do
            while IFS= read -r line; do
                if echo "$line" | grep -qi "$prefix"; then
                    ip=$(echo "$line" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | head -1)
                    if [ -n "$ip" ]; then
                        already_found=false
                        for found in "${FOUND_PIS[@]}"; do
                            if [[ "$found" == "$ip|"* ]]; then
                                already_found=true
                                break
                            fi
                        done
                        if [ "$already_found" = false ]; then
                            echo -e "  ${GREEN}✓${NC} Found: $ip (Raspberry Pi MAC address)"
                            FOUND_PIS+=("$ip||ARP")
                        fi
                    fi
                fi
            done <<< "$arp_output"
        done
    fi
fi

echo ""

# Display results
if [ ${#FOUND_PIS[@]} -eq 0 ]; then
    echo -e "${YELLOW}══════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  No Raspberry Pi devices found automatically.${NC}"
    echo -e "${YELLOW}══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${CYAN}Diagnostic info:${NC}"
    echo -e "  • Your IP: ${LOCAL_IP:-unknown}"
    echo -e "  • Subnet scanned: ${SUBNET:-unknown}.0/24"
    echo ""

    # Show ARP table snippet for debugging
    echo -e "  ${CYAN}Devices on your network (ARP table):${NC}"
    if command -v arp &> /dev/null; then
        arp -a 2>/dev/null | head -10 | while read line; do
            echo -e "    $line"
        done
        arp_count=$(arp -a 2>/dev/null | wc -l | tr -d ' ')
        echo -e "    ... ($arp_count total devices)"
    else
        echo -e "    (arp command not available)"
    fi
    echo ""

    echo -e "  ${YELLOW}Possible reasons:${NC}"
    echo -e "  • Pi is on a different network/VLAN"
    echo -e "  • Pi has a non-standard MAC address"
    echo -e "  • Pi hostname was changed from default"
    echo ""
    echo -e "  ${CYAN}Try manually:${NC}"
    echo -e "  • Check your router's admin page for connected devices"
    echo -e "  • Look for a device named 'raspberrypi' or similar"
    echo ""
    echo -e "  ${CYAN}Or if you know your Pi's IP, connect directly:${NC}"
    echo -e "  ${GREEN}ssh pi@<YOUR_PI_IP>${NC}"
    echo ""
else
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Found ${#FOUND_PIS[@]} Raspberry Pi device(s)!${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo ""

    # Display found Pis with numbers for selection
    index=1
    for found in "${FOUND_PIS[@]}"; do
        IFS='|' read -r ip hostname method <<< "$found"
        if [ -n "$hostname" ]; then
            echo -e "  ${CYAN}[$index]${NC} $ip ($hostname)"
        else
            echo -e "  ${CYAN}[$index]${NC} $ip"
        fi
        ((index++))
    done

    echo ""

    # Select Pi if multiple found
    SELECTED_IP=""
    if [ ${#FOUND_PIS[@]} -eq 1 ]; then
        SELECTED_IP=$(echo "${FOUND_PIS[0]}" | cut -d'|' -f1)
    else
        echo -e "  ${BLUE}Which Pi do you want to connect to?${NC}"
        echo -n "  Enter number [1-${#FOUND_PIS[@]}]: "
        read -r selection < /dev/tty

        if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#FOUND_PIS[@]} ]; then
            SELECTED_IP=$(echo "${FOUND_PIS[$((selection-1))]}" | cut -d'|' -f1)
        else
            echo -e "  ${YELLOW}Invalid selection. Using first Pi.${NC}"
            SELECTED_IP=$(echo "${FOUND_PIS[0]}" | cut -d'|' -f1)
        fi
    fi

    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Connecting to $SELECTED_IP...${NC}"
    echo -e "${GREEN}══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${YELLOW}Default username:${NC} pi"
    echo -e "  ${YELLOW}Default password:${NC} raspberry (change it after!)"
    echo ""
    echo -e "  ${BLUE}Once connected, the installer will run automatically.${NC}"
    echo ""

    # SSH in and run the installer (exec to properly handle stdin/tty)
    exec ssh -t "pi@$SELECTED_IP" "curl -sSL https://pihole-wizard.com/install.sh | bash" < /dev/tty
fi
